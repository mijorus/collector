import os
import logging
import base64
from PIL import Image

from gi.repository import Gtk, Adw, Gio, GLib, Gdk

from .constants import APP_ID, SUPPORTED_IMG_TYPES
from .utils import get_giofile_content_type, \
    pillow_crop_center, get_file_hash, \
    link_is_image, download_file, get_safe_path, \
    get_random_string, get_gsettings
    

class DroppedItemNotSupportedException(Exception):
    def __init__(self, item, msg, *args: object) -> None:
        super().__init__(*args)
        self.item = item

        logging.warn(msg)

class DroppedItem():
    MAX_PREVIEW_SIZE_MB = 50

    def __init__(self, item, drops_dir, dynamic_size=False, is_clipboard=False) -> None:
        self.DROPS_DIR = drops_dir

        self.received_item = item
        self.target_path = None
        self.display_value = ''
        self.preview_image: Gio.File or str = 'paper-symbolic'
        self.gfile = None
        self.size = 0
        self.async_load = False
        self.dynamic_size = dynamic_size
        self.content_is_text = False
        self.is_clipboard = is_clipboard

        logging.debug(f'Creating item from type: {type(item)}')

        if item == None:
            raise DroppedItemNotSupportedException(msg=f'item of type None not supported')

        if isinstance(item, Gdk.Texture):
            item = self.create_tmp_file_from_texture(item)
        elif isinstance(item, Gio.File) and not item.get_path() and item.get_uri():
            # detect if is a dummy file
            item = item.get_uri()
            self.received_item = item

        if isinstance(item, Gio.File):
            self.gfile = item
            self.target_path = item.get_path()
            self.display_value = item.get_basename()  
            self.size = self.get_size(True)
            self.generate_preview_for_image()

        elif isinstance(item, str):
            base_filename = 'collected_text_'
            text_string = item
            self.content_is_text = True

            self.preview_image = 'font-x-generic-symbolic'
            if text_string.startswith('http://') or text_string.startswith('https://'):
                logging.debug(f'Found http url: {text_string}')
                base_filename = 'collected_link_'
                self.async_load = True
                self.preview_image = 'chain-link-symbolic'


            self.target_path = get_safe_path(f'{self.DROPS_DIR}/{base_filename}', 'txt')
            with open(self.target_path, 'w+') as f:
                f.write(text_string)

            self.gfile = Gio.File.new_for_path(self.target_path)
            self.size = len(text_string)

            self.set_display_value(text_string)

        else:
            raise DroppedItemNotSupportedException(msg=f'item of type {type(item)} not supported')
        
        if self.is_clipboard:
            self.preview_image = 'notepad-symbolic'
    
    def get_size(self, force=False):
        if not force and not self.dynamic_size:
            return self.size
        
        return self.gfile.query_info('standard::', Gio.FileQueryInfoFlags.NONE, None).get_size()

    def get_text_content(self):
        if self.content_is_text:
            with open(self.target_path, 'r') as f:
                return f.read()
        else:
            with open(self.target_path, 'rb') as f:
                return base64.b64encode(f.read()).decode()

    def complete_load(self):
        logging.debug(f'Completing load for {self.received_item}')

        if not self.async_load:
            return
        
        if isinstance(self.received_item, str):
            settings = get_gsettings()
            should_download_images = settings.get_boolean('download-images')

            if not should_download_images:
                return

            text_content = ''
            with open(self.gfile.get_path(), 'r') as f:
                text_content = f.read()

            (is_image, img_link) = link_is_image(text_content)

            if not is_image:
                logging.debug(f'URL does not seem to be an image: {img_link}')
                return

            try:
                data, filename, content_type = download_file(img_link)
            except Exception as e:
                logging.warn(e)
                return
            
            # write tmp file: this ensures support for binary files
            # to be downloaded and analysed
            tmp_path = f'{self.DROPS_DIR}/{get_random_string(10)}'
            with open(tmp_path, 'wb') as f:
                f.write(data)

            tmp_file = Gio.file_new_for_path(tmp_path)
            tmp_file_content_type = get_giofile_content_type(tmp_file)

            if not tmp_file_content_type in SUPPORTED_IMG_TYPES:
                tmp_file.delete(None)
                return
            
            extension = tmp_file_content_type.split('/')[1]
            if extension == 'svg+xml':
                extension = 'svg'

            base_name = os.path.splitext(filename)[0]
            self.target_path = get_safe_path(f'{self.DROPS_DIR}/{base_name}', extension)

            self.gfile = Gio.File.new_for_path(self.target_path)
            tmp_file.move(self.gfile, Gio.FileCopyFlags.OVERWRITE)

            self.display_value = self.set_display_value(img_link)
            self.size = self.get_size(True)

            self.generate_preview_for_image()

        self.async_load = False

    def generate_preview_for_image(self):
        content_type = get_giofile_content_type(self.gfile)

        if content_type in SUPPORTED_IMG_TYPES and self.size < (self.MAX_PREVIEW_SIZE_MB * (1024 * 1024)):
            logging.debug(f'Generating preview image for: {self.target_path}')

            extension = os.path.splitext(self.target_path)[1]

            filehash = get_file_hash(self.gfile)
            preview_path = f'{self.DROPS_DIR}/__{filehash}.{extension}'

            if content_type not in ['image/svg', 'image/svg+xml']:
                image = self.crop_image(self.target_path)
                image.save(preview_path, format='png')
                self.preview_image = Gio.File.new_for_path(preview_path)
            else:
                self.preview_image = self.gfile
        else:
            info = self.gfile.query_info('standard::icon' , 0 , Gio.Cancellable())
            self.preview_image = info.get_icon()

    def crop_image(self, image_path):
        logging.debug(f'Cropping image: {image_path}')

        image = Image.open(image_path)
        image.thumbnail((200, 200))
        image = pillow_crop_center(image, min(image.size))
        return image
    
    def create_tmp_file_from_texture(self, texture: Gdk.Texture):
        tmp_filename = get_safe_path(f'{self.DROPS_DIR}/collected_image_', '.png')
        texture.save_to_png(tmp_filename)

        file = Gio.File.new_for_path(tmp_filename)
        return file

    def set_display_value(self, text):
        self.display_value = text[:25]
        if len(text) > 26:
            self.display_value = self.display_value + '...'