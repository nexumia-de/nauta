"""Swipe a row from right to left for a quick action (docs/library.md):
the row's content follows the finger and uncovers an icon; past a third
of the width the action runs when the finger is lifted. Left-to-right
stays libadwaita's swipe back (phosh-toolkit adaptive rule 9)."""
from gi.repository import Graphene, Gsk, Gtk

# Pixels the finger moves sideways before the row takes the drag.
START = 16
# Share of the width past which lifting the finger runs the action.
THRESHOLD = 1 / 3


class SwipeBox(Gtk.Widget):
    """Holds `child`; a right-to-left swipe calls on_swipe()."""

    def __init__(self, child, icon, label, on_swipe):
        super().__init__()
        self.on_swipe = on_swipe
        self.offset = 0.0
        self.under = Gtk.Box(halign=Gtk.Align.END)
        self.under.add_css_class("nauta-swipe")
        image = Gtk.Image(icon_name=icon, margin_start=18, margin_end=18,
                          valign=Gtk.Align.CENTER, vexpand=True)
        image.set_tooltip_text(label)
        self.under.append(image)
        self.under.set_parent(self)
        self.under.set_visible(False)
        self.child = child
        child.set_parent(self)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        drag = Gtk.GestureDrag()
        drag.connect("drag-update", self._on_update)
        drag.connect("drag-end", self._on_end)
        self.add_controller(drag)
        self._taken = False

    # --- layout -------------------------------------------------------

    def do_measure(self, orientation, for_size):
        return self.child.measure(orientation, for_size)[:4]

    def do_size_allocate(self, width, height, baseline):
        shift = Gsk.Transform().translate(Graphene.Point().init(self.offset, 0))
        self.child.allocate(width, height, baseline, shift)
        uncovered = int(min(width, -self.offset))
        self.under.set_visible(uncovered > 0)
        if uncovered > 0:
            need = self.under.measure(Gtk.Orientation.HORIZONTAL, height)[0]
            self.under.allocate(max(uncovered, need), height, baseline,
                                Gsk.Transform().translate(Graphene.Point().init(
                                    width - max(uncovered, need), 0)))
        else:
            self.under.allocate(1, height, baseline, None)

    def do_dispose(self):
        for child in (getattr(self, "under", None), getattr(self, "child", None)):
            if child is not None and child.get_parent() is self:
                child.unparent()
        Gtk.Widget.do_dispose(self)

    # --- gesture ------------------------------------------------------

    def _on_update(self, gesture, dx, dy):
        if not self._taken:
            if dx > -START or abs(dx) < 2 * abs(dy):
                return
            self._taken = True
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.offset = min(0.0, dx)
        self.under.set_opacity(1 if self._past() else 0.5)
        self.queue_allocate()

    def _on_end(self, gesture, dx, dy):
        if not self._taken:
            return
        run = self._past()
        self._taken = False
        self.offset = 0.0
        self.queue_allocate()
        if run:
            self.on_swipe()

    def _past(self):
        return -self.offset >= self.get_width() * THRESHOLD
