import os
import logging
from PIL import Image
from gi.repository import Gtk, Adw, Gio, GLib, GObject

from .utils import get_giofile_content_type, \
    pillow_crop_center, get_file_hash, \
    link_is_image, download_image, get_safe_path

class DroppedItemNotSupportedException(Exception):
    def __init__(self, item, *args: object) -> None:
        super().__init__(*args)
        self.item = item

class DroppedItem():
    
    DROPS_DIR = f'{GLib.get_user_cache_dir()}/drops'

    def __init__(self, item) -> None:
        self.target_path = None
        self.display_value = ''
        self.preview_image = 'paper-symbolic'
        self.gfile = None
        self.size = 0
        self.async_load = False

        MAX_PREVIEW_SIZE_MB = 50

        if isinstance(item, Gio.File):
            self.gfile = item
            self.target_path = item.get_path()
            self.display_value = item.get_basename()            
            info = item.query_info('standard::icon' , 0 , Gio.Cancellable())
            self.size = os.stat(item.get_path()).st_size

            content_type = get_giofile_content_type(item)
            if content_type in ['image/png', 'image/jpg', 'image/jpeg'] and self.size < (MAX_PREVIEW_SIZE_MB * (1024 * 1024)):
                self.generate_preview_for_image()
            else:
                self.preview_image = info.get_icon()
        elif isinstance(item, str):
            base_filename = 'collected_text_'
            text_string = item

            if text_string.startswith('http://') or text_string.startswith('https://'):
                self.async_load = True

            self.target_path = get_safe_path(f'{self.DROPS_DIR}/{base_filename}', 'txt')
            with open(self.target_path, 'w+') as f:
                f.write(text_string)

            self.gfile = Gio.File.new_for_path(self.target_path)
            self.size = len(text_string)
            self.preview_image = 'font-x-generic-symbolic'

            self.display_value = text_string[:25]
            if len(item) > 26:
                self.display_value = self.display_value + '...'

        else:
            raise DroppedItemNotSupportedException(item)
    
    def complete_load(self):
        if not self.async_load:
            return
        
        text_content = ''
        with open(self.gfile.get_path(), 'r') as f:
            text_content = f.read()
        
        try:
            is_image = link_is_image(text_content)
        except Exception as e:
            logging.warn(e)
            return

        if not is_image:
            return
        
        try:
            data, extension, filename = download_image(text_content)
        except Exception as e:
            logging.warn(e)
            return
        
        self.target_path = get_safe_path(f'{self.DROPS_DIR}/{filename}', extension)

        with open(self.target_path, 'wb') as f:
            f.write(data)

        self.gfile = Gio.File.new_for_path(self.target_path)

        self.generate_preview_for_image()
        self.async_load = False

    def generate_preview_for_image(self):
        logging.debug(f'Generating preview image for: {self.target_path}')

        extension = os.path.splitext(self.target_path)[1]

        filehash = get_file_hash(self.gfile)
        preview_path = f'{self.DROPS_DIR}/__{filehash}.{extension}'

        image = self.crop_image(self.target_path)
        image.save(preview_path)

        self.preview_image = Gio.File.new_for_path(preview_path)


        
    def crop_image(self, image_path):
        logging.debug(f'Cropping image: {image_path}')

        image = Image.open(image_path)
        image.thumbnail((200, 200))
        image = pillow_crop_center(image, min(image.size))
        return image