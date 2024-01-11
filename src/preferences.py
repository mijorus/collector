import os
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio


@Gtk.Template(resource_path='/it/mijorus/collector/gtk/preferences.ui')
class SettingsWindow(Adw.PreferencesWindow):
    """ settings dialog """
    __gtype_name__ = "SettingsWindow"

    def __init__(self):
        super().__init__()