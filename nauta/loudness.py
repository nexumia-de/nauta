"""Volume normalisation with ReplayGain (docs/playback.md): GStreamer's
rgvolume as playbin's audio filter reads the ReplayGain tags in the
stream and evens out the loudness. No widgets."""
import logging

from gi.repository import Gst

log = logging.getLogger("nauta.loudness")

OFF, TRACK, ALBUM = "off", "track", "album"
# (setting, name in the preferences)
MODES = ((OFF, "Off"), (TRACK, "Same Loudness for Every Song"),
         (ALBUM, "Same Loudness for Every Album"))
# Gain for files without ReplayGain tags, in dB: a little quieter, as
# tagged songs are usually lowered to about -18 LUFS too.
FALLBACK_GAIN = -6.0


def apply(media, mode):
    """Put rgvolume in front of the sound output of a phosh_toolkit
    Media; nothing for OFF or when the element is missing."""
    if mode not in (TRACK, ALBUM) or media.pipeline is None:
        return False
    element = Gst.ElementFactory.make("rgvolume", None)
    if element is None:
        log.info("rgvolume missing, no volume normalisation")
        return False
    element.props.album_mode = mode == ALBUM
    element.props.fallback_gain = FALLBACK_GAIN
    # Keep peaks below full scale instead of clipping.
    element.props.headroom = 0.0
    media.pipeline.props.audio_filter = element
    return True
