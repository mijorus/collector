import os

from PIL import Image
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from .utils import get_giofile_content_type, pillow_crop_center, get_file_hash

class DroppedItemNotSupportedException(Exception):
    def __init__(self, item, *args: object) -> None:
        super().__init__(*args)
        self.item = item

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
            self.size = os.stat(item.get_path()).st_size

            content_type = get_giofile_content_type(item)
            if content_type in ['image/png', 'image/jpg', 'image/jpeg']:
                filehash = get_file_hash(item)
                preview_path = f'{ GLib.get_user_cache_dir()}/drops/{filehash}.{content_type.split("/")[1]}'
                image = Image.open(self.target_path)
                image.thumbnail((200, 200))
                image = pillow_crop_center(image, min(image.size))
                image.save(preview_path)

                self.preview_image = Gtk.Image(
                    file=preview_path,
                    overflow=Gtk.Overflow.HIDDEN,
                    css_classes=['dropped-item-thumb'],
                    height_request=70,
                    width_request=70,
                )
            else:
                self.preview_image = info.get_icon()
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
            self.preview_image = 'font-x-generic-symbolic'

            self.display_value = text_string[:25]
            if len(item) > 26:
                self.display_value = self.display_value + '...'

        else:
            raise DroppedItemNotSupportedException(item)