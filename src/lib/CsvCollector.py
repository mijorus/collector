import csv
import os
from typing import Optional
from gi.repository import Gio

from .DroppedItem import DroppedItem
from .utils import get_safe_path

class CsvCollector():
    def __init__(self, drop_dir) -> None:
        self.DROP_DIR = drop_dir
        self.dropped_item: Optional[DroppedItem] = None
        self.FILENAME = get_safe_path(f'{drop_dir}/collected_strings_', 'csv')

        with open(self.FILENAME, 'w+') as f:
            f.write('')

    def append_text(self, text: str):
        with open(self.FILENAME, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([text])

            f.close()

    def get_gfile(self):
        return Gio.File.new_for_path(self.FILENAME)
    
    def set_dropped_item(self, d: DroppedItem):
        self.dropped_item = d

    def delete_file(self):
        self.dropped_item = None

        if os.path.exists(self.FILENAME):
            os.remove(self.FILENAME)
