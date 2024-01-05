import os
import hashlib
import logging
import random
import string
import requests
import re
import urllib
from .constants import APP_ID, SUPPORTED_IMG_TYPES, IMAGE_EXT_FORMATS
from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib

google_re = re.compile(
    "[http|https]:\/\/www.google.com\/imgres\?imgurl=(.*)\&imgrefurl"
)

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
        
def link_is_image(link) -> tuple[bool, str]:
    logging.info(f'Testing link headers for: {link}')

    link = link.strip()
    settings = Gio.Settings(APP_ID)
    MAX_SIZE_MB_FOR_BINARIES = 25
    
    file_ext = link.split('.')[-1]
    print(file_ext)

    if settings.get_boolean('google-images-support'):   
        is_google_image = google_re.findall(link)

        if is_google_image:
            link = urllib.parse.unquote(is_google_image[0])

    r = requests.head(link)
    is_image = r.headers.get("content-type", None) in SUPPORTED_IMG_TYPES

    if is_image:
        logging.info(f'Link appears to be an image')
    elif r.headers["content-type"] == 'binary/octet-stream' and \
            file_ext in IMAGE_EXT_FORMATS:

        logging.debug(f'Link is a binary/octet-stream, but trusting the file extension: {file_ext}')

        item_size = r.headers.get('content-length', 0)
        item_size = int(item_size)

        if item_size and item_size < MAX_SIZE_MB_FOR_BINARIES * (1024 * 1024):
            is_image = True

    return (is_image, link)

# def download_image(link: str):
#     logging.debug(f'Downloading image from url: {link}')
#     r = requests.get(link.strip())

#     extension = r.headers["content-type"].split('/')[1]
#     filename = link.split('/')[-1]

#     if r.headers.get('content-disposition', None):
#         d = r.headers['content-disposition']
#         filename = re.findall("filename=(.+)", d)[0]

#     extension = extension.split('+')[0]
#     return (r.content, extension, filename)

def download_file(link: str):
    logging.debug(f'Downloading file from url: {link}')
    r = requests.get(link.strip(), timeout=30)

    ct = r.headers.get("content-type", '')
    filename = link.split('/')[-1]

    if r.headers.get('content-disposition', None):
        d = r.headers.get('content-disposition', None)

        if d:
            filename = re.findall("filename=(.+)", d)[0]

    return (r.content, filename, ct)

def get_safe_path(p, ext):
    i = 1
    while os.path.exists(f'{p}{i}.{ext}'):
        i += 1

    return f'{p}{i}.{ext}'

def get_random_string(length):
    result_str = ''.join(random.choice(string.ascii_letters) for i in range(length))
    return result_str