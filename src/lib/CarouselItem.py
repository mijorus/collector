import gi
from typing import Optional

from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib

from .DroppedItem import DroppedItem

class CarouselItem():
    def __init__(self, item: DroppedItem, image: Gtk.Image, index: int):
        self.image = image
        self.dropped_item = item
        self.index = index