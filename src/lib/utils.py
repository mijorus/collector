import hashlib
from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib


def get_giofile_content_type(file: Gio.File):
    return file.query_info('standard::', Gio.FileQueryInfoFlags.NONE, None).get_content_type()

def pillow_crop_center(pil_img, size):
    img_width, img_height = pil_img.size
    return pil_img.crop(((img_width - size) // 2,
                         (img_height - size) // 2,
                         (img_width + size) // 2,
                         (img_height + size) // 2))

def get_file_hash(file: Gio.File, alg='md5') -> str:
    with open(file.get_path(), 'rb') as f:
        if alg == 'md5':
            return hashlib.md5(f.read()).hexdigest()
        elif alg == 'sha1':
            return hashlib.sha1(f.read()).hexdigest()