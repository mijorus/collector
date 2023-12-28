from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib


def get_giofile_content_type(file: Gio.File):
    return file.query_info('standard::', Gio.FileQueryInfoFlags.NONE, None).get_content_type()