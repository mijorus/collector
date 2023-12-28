import os
from gi.repository import Gtk, Adw, Gio, GLib, GObject

class DroppedItemNotSupportedException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class DroppedItem():
    def __init__(self, item) -> None:
        self.target_path = None
        self.display_value = ''
        self.preview_image = Gtk.Image(icon_name='paper-symbolic', pixel_size=70)
        self.item = item

        if isinstance(item, Gio.File):
            self.target_path = item.get_path()
            print(self.target_path)
            self.display_value = item.get_basename()            
            info = item.query_info('standard::icon' , 0 , Gio.Cancellable())
            self.preview_image.set_from_gicon(info.get_icon())

        elif isinstance(item, str):
            base_filename = 'collected_text_'
            text_string = item

            i = 1
            while os.path.exists(GLib.get_user_cache_dir() + f'/drops/{base_filename}{i}.txt'):
                i += 1

            self.target_path = GLib.get_user_cache_dir() + f'/drops/{base_filename}{i}.txt'
            with open(self.target_path, 'w+') as f:
                f.write(text_string)

            self.preview_image.set_from_icon_name('text-justify-left-symbolic')

            self.display_value = text_string[:15]
            if len(item) > 16:
                self.display_value = self.display_value + '...'

        else:
            raise DroppedItemNotSupportedException()