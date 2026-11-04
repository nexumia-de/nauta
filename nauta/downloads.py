"""The download server: the user's MeTube, reached like the music server
(local address on a listed home Wi-Fi, remote address elsewhere, client
certificate, the proxy's own login), and the downloads Nauta started
(docs/downloads.md). No GTK."""
import logging

from gi.repository import GLib, GObject
from phosh_toolkit import tasks, tls
from phosh_toolkit.http import NETWORK, HttpError
from phosh_toolkit.proxy_login import CookieJar, ProxyCredentials
from phosh_toolkit.router import Router

from nauta import keyring, settings
from nauta.keyring import CREDENTIALS
from nauta.metube import ACTIVE, SONGS, YOUTUBE, MeTube, matches
from nauta.ytmusic import YouTubeMusic

log = logging.getLogger("nauta.downloads")

# Seconds between two looks at MeTube's list while a page shows it or a
# download Nauta started is running.
POLL = 2


class Downloads(Router):
    __gsignals__ = {
        # MeTube's list ({"queue", "pending", "done"}) after each look.
        "history": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        # A download Nauta started, a song or a whole album or playlist:
        # finished (title) or failed (title, message).
        "finished": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "failed": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    # MeTube can't say who it is (no server id), so the local address is
    # used only on a listed home Wi-Fi, as for the music server.
    strict_local = True

    def __init__(self, store=None, watch=True):
        super().__init__(watch=watch)
        self.store = store or settings.DownloadStore()
        self.account = self.store.load()
        self.api = MeTube()
        # Albums and playlists are searched from the phone, with its own
        # HTTP client: nothing of the download server's login goes there.
        self.youtube_music = YouTubeMusic()
        self.certificate_error = None
        self.load_certificate()
        self.proxy_cookies = CookieJar(keyring.DOWNLOADS)
        self.proxy_credentials = ProxyCredentials(keyring.DOWNLOADS)
        self.load_proxy_login()
        self.history = None
        self._watchers = 0
        # url -> [(title, timestamps of older items, _Group or None)]: a
        # song can be part of two albums or playlists being downloaded.
        self._mine = {}
        self._timer = 0
        self._polling = False

    @property
    def configured(self):
        return self.account.configured

    def load_certificate(self):
        self.certificate_error = None
        self.api.http.certificate = None
        if not self.account.certificate:
            return
        try:
            self.api.http.certificate = settings.download_certificates().load()
        except (OSError, tls.CertificateError) as e:
            self.certificate_error = str(e)
            log.warning("download server certificate: %s", e)

    def save(self):
        self.store.save(self.account)

    def load_proxy_login(self):
        self.api.http.cookies = self.proxy_cookies.load()
        self.api.http.proxy_auth = self.proxy_credentials.headers()

    def reconnect(self):
        """After the address or certificate changed."""
        self.load_certificate()
        self.load_proxy_login()
        self.base_url = self.api.base_url = ""
        self.history = None
        if self.configured:
            self.resolve()

    def forget(self):
        """Remove the download server: addresses, certificate, proxy
        login."""
        settings.download_certificates().delete()
        self.proxy_cookies.save({})
        keyring.DOWNLOADS.clear(CREDENTIALS)
        self.account = settings.DownloadServer(
            audio_format=self.account.audio_format, source=self.account.source,
            kind=self.account.kind)
        self.save()
        self.reconnect()

    # --- Router ------------------------------------------------------

    def probe(self, url, timeout):
        return probe_with(self.api.http)(url, timeout)

    def addresses(self):
        a = self.account
        return a.remote_url, a.local_url, a.home_networks

    def resolve(self, done=None):
        if not self.configured:
            if done:
                done(HttpError(NETWORK, "No download server"))
            return
        super().resolve(done)

    def resolved(self, kind, url, info):
        self.api.base_url = url

    # --- calls -------------------------------------------------------

    def search(self, query, source, kind, done):
        """Songs or videos through MeTube; albums and playlists of YouTube
        Music straight from YouTube Music, which needs no download server
        (nauta.ytmusic)."""
        if source == YOUTUBE or kind == SONGS:
            self.call(self.api.search, done, query, source)
        else:
            tasks.run(self.youtube_music.search, done, query, kind)

    def browse(self, url, done):
        """The songs of an album or playlist: done((title, entries), error)."""
        self.call(self.api.browse, done, url)

    def add(self, url, title, done, songs=None):
        """Queue `url` in the chosen format; done(answer, error). Its end
        is reported with "finished" or "failed". For an album or playlist,
        `songs` are its entries from browse(): Nauta follows them and
        reports the whole once, under `title`."""
        audio_format = self.account.audio_format
        urls = [s["url"] for s in songs] if songs else [url]

        def work():
            # Items of the same URL already in the list are older
            # downloads, not this one.
            history = self.api.history()["done"]
            before = {u: {i.get("timestamp") for i in history if matches(i, u)}
                      for u in urls}
            answer = self.api.add(url, audio_format)
            return answer, before

        def finished(result, error):
            if error is None:
                answer, before = result
                if songs:
                    group = _Group(title, len(urls))
                    titles = {s["url"]: s.get("title") or s["url"] for s in songs}
                    for u in urls:
                        self._mine.setdefault(u, []).append(
                            (titles[u], before[u], group))
                else:
                    self._mine.setdefault(url, []).append(
                        (title, before[url], None))
                self._schedule()
                done(answer, None)
            else:
                done(None, error)
        self.call(work, finished)

    def remove(self, items, where, done):
        # MeTube keys its lists by the item's URL.
        ids = [i.get("url") for i in items]
        self.call(self.api.delete, lambda r, e: (done(r, e), self.refresh()),
                  ids, where)

    # --- watching the list -------------------------------------------

    def watch(self):
        """A page shows the list: look at it now and every POLL seconds."""
        self._watchers += 1
        self.refresh()

    def unwatch(self):
        self._watchers = max(0, self._watchers - 1)

    def refresh(self):
        if self.configured and not self._polling:
            self._polling = True
            self.call(self.api.history, self._on_history)

    def _wanted(self):
        return self.configured and (self._watchers > 0 or bool(self._mine))

    def _schedule(self):
        if self._timer == 0 and self._wanted():
            self._timer = GLib.timeout_add_seconds(POLL, self._on_timer)

    def _on_timer(self):
        self._timer = 0
        if self._wanted():
            self.refresh()
        return GLib.SOURCE_REMOVE

    def _on_history(self, history, error):
        self._polling = False
        if error is None:
            self.history = history
            self._check_mine(history)
            self.emit("history", history)
        else:
            log.info("download list: %s", error)
            self.emit("history", None)
        self._schedule()

    def _check_mine(self, history):
        for url, jobs in list(self._mine.items()):
            for title, before, group in list(jobs):
                self._check_job(history, url, jobs, title, before, group)
            if not jobs:
                del self._mine[url]

    def _check_job(self, history, url, jobs, title, before, group):
        for item in history["done"]:
            if matches(item, url) and item.get("timestamp") not in before:
                jobs.remove((title, before, group))
                if item.get("status") == "finished":
                    self._report(group, title, None)
                else:
                    self._report(group, title, item.get("msg") or
                                 item.get("error") or "Download failed")
                return
        active = any(matches(i, url) for k in ("queue", "pending")
                     for i in history[k])
        if not active and not any(matches(i, url) for i in history["done"]):
            # Gone from the list (cancelled elsewhere, or left out of an
            # album by MeTube).
            jobs.remove((title, before, group))
            if group is not None:
                group.left -= 1
                self._report_group(group)

    def _report(self, group, title, message):
        if group is None:
            if message is None:
                self.emit("finished", title)
            else:
                self.emit("failed", title, message)
            return
        group.left -= 1
        if message is not None:
            group.failed.append(message)
        self._report_group(group)

    def _report_group(self, group):
        if group.left > 0:
            return
        if not group.failed:
            self.emit("finished", group.title)
        elif len(group.failed) == group.total:
            self.emit("failed", group.title, group.failed[0])
        else:
            n = len(group.failed)
            self.emit("failed", group.title,
                      f"{n} of {group.total} songs failed ({group.failed[0]})")


class _Group:
    """An album or playlist downloaded at once: reported when the last
    of its songs is done."""

    def __init__(self, title, total):
        self.title = title
        self.total = self.left = total
        self.failed = []


def is_active(item):
    return item.get("status") in ACTIVE


def probe_with(http):
    """Ask MeTube's /version through `http`; MeTube has no server id."""
    def probe(url, timeout):
        return "", MeTube(http).probe(url, timeout=timeout)
    return probe


def probe_through(http, url, timeout):
    """The probe in the form phosh_toolkit.proxy_login wants."""
    return probe_with(http)(url, timeout)
