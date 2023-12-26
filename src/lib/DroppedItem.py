from gi.repository import Gtk, Adw, Gio, Gdk, GObject

class DroppedItem():
    def __init__(self, item) -> None:
        self.target_path = None
        self.display_value = ''
        self.preview_image = Gtk.Image(icon_name='paper-symbolic', pixel_size=70)

        if isinstance(item, Gio.File):
            self.target_path = item.get_path()
            self.display_value = item.get_basename()            
            info = item.query_info('standard::icon' , 0 , Gio.Cancellable())
            self.preview_image.set_from_gicon(info.get_icon())

        elif isinstance(item, GObject.TYPE_STRING):
            self.preview_image.set_from_icon_name('text-justify-left-symbolic')
            self.display_value = '...'
