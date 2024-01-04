import os
import hashlib
import logging
import requests
import re
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
        
def link_is_image(link):
    logging.info(f'Testing link headers for: {link}')     

    link = link.strip()
    image_formats = ["image/png", "image/jpeg", "image/jpg"]
    r = requests.head(link)
    
    is_image = r.headers["content-type"] in image_formats

    if is_image:
        logging.info(f'Link appears to be an image')     

    return is_image


def download_image(link: str):
    logging.log(f'Downloading image from url: {link}')
    r = requests.get(link.strip())

    extension = r.headers["content-type"].split('/')[1]
    filename = link.split('/')[-1]

    if r.headers.get('content-disposition', None):
        d = r.headers['content-disposition']
        filename = re.findall("filename=(.+)", d)[0]


    return (r.content(), extension, filename)


def get_safe_path(p, ext):
    i = 1
    while os.path.exists(f'{p}{i}.{ext}'):
        i += 1

    return f'{p}{i}.{ext}'