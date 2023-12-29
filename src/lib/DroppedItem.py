import os
from gi.repository import Gtk, Adw, Gio, GLib, GObject

class DroppedItemNotSupportedException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class DroppedItem():
    def __init__(self, item) -> None:
        self.target_path = None
        self.display_value = ''
        self.preview_image = 'paper-symbolic'
        self.gfile = None
        self.size = 0

        if isinstance(item, Gio.File):
            self.gfile = item
            self.target_path = item.get_path()
            self.display_value = item.get_basename()            
            info = item.query_info('standard::icon' , 0 , Gio.Cancellable())
            self.preview_image = info.get_icon()
            self.size = os.stat(item.get_path()).st_size

        elif isinstance(item, str):
            base_filename = 'collected_text_'
            text_string = item

            i = 1
            while os.path.exists(GLib.get_user_cache_dir() + f'/drops/{base_filename}{i}.txt'):
                i += 1

            self.target_path = GLib.get_user_cache_dir() + f'/drops/{base_filename}{i}.txt'
            with open(self.target_path, 'w+') as f:
                f.write(text_string)

            self.gfile = Gio.File.new_for_path(self.target_path)
            self.size = os.stat(self.target_path).st_size
            self.preview_image = 'text-justify-left-symbolic'

            self.display_value = text_string[:15]
            if len(item) > 16:
                self.display_value = self.display_value + '...'

        else:
            raise DroppedItemNotSupportedException()