import os
import gi

from .lib.utils import get_gsettings
from .lib.constants import SUPPORTED_IMG_TYPES, APP_ID

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio


@Gtk.Template(resource_path='/it/mijorus/collector/gtk/preferences.ui')
class SettingsWindow(Adw.PreferencesWindow):
    """ settings dialog """
    __gtype_name__ = "SettingsWindow"

    keep_items_when_dragging = Gtk.Template.Child()
    download_images_row = Gtk.Template.Child()
    download_images = Gtk.Template.Child()
    text_as_csv = Gtk.Template.Child()
    open_gnome_ext = Gtk.Template.Child()
    configure_kde = Gtk.Template.Child()
    launch_shortcut = Gtk.Template.Child()
    launch_shortcut_windows = Gtk.Template.Child()
    google_images_support = Gtk.Template.Child()
    debug_logs = Gtk.Template.Child()

    def __init__(self):
        super().__init__()

        self.settings = get_gsettings()

        self.settings.bind('keep-on-drag', self.keep_items_when_dragging,
                           'active', Gio.SettingsBindFlags.DEFAULT)
        
        self.settings.bind('google-images-support', self.google_images_support, 
        'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('download-images', self.download_images, 
        'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('collect-text-to-csv', self.text_as_csv, 
        'active', Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind('debug-logs', self.debug_logs, 
        'active', Gio.SettingsBindFlags.DEFAULT)

        download_images_sbt = self.download_images_row.get_subtitle()
        suported_formats_str = '\n\n' + _('The following image formats are currently supported: ')
        suported_formats_str += ', '.join([s.split('/')[1] for s in SUPPORTED_IMG_TYPES])
        self.download_images_row.set_subtitle(download_images_sbt + suported_formats_str)

        self.launch_shortcut_windows.connect('notify::selected', self.on_launch_shortcuts_wd_changed)

        self.launch_shortcut.set_label(f'flatpak run {APP_ID}')

    def on_launch_shortcuts_wd_changed(self, w: Adw.ComboRow, val):
        val = w.get_selected() + 1
        
        if val > 1:
            self.launch_shortcut.set_label(f'flatpak run {APP_ID} -w={val}')
        else:
            self.launch_shortcut.set_label(f'flatpak run {APP_ID}')