import csv
import os
from typing import Optional
from gi.repository import Gio, Adw, Gtk, Gdk

from .DroppedItem import DroppedItem
from .utils import get_safe_path

class CsvCollector():
    def __init__(self, drop_dir) -> None:
        self.DROP_DIR = drop_dir
        self.FILENAME = get_safe_path(f'{drop_dir}/collected_strings_', 'csv')
        self.text_pieces = 0

        with open(self.FILENAME, 'w+') as f:
            f.write('')

    def append_text(self, text: str):
        self.text_pieces += 1
        with open(self.FILENAME, 'a') as f:
            writer = csv.writer(f)
            writer.writerow([text])

            f.close()

    def get_gfile(self):
        return Gio.File.new_for_path(self.FILENAME)

    def clear(self):
        self.text_pieces = 0
        if os.path.exists(self.FILENAME):
            os.remove(self.FILENAME)

    def on_copy_btn_clicked(self, w: Gtk.Button, data):
        cp = Gdk.Display.get_default().get_clipboard()
        content_prov = Gdk.ContentProvider.new_for_value(data)
        cp.set_content(content_prov)

    def get_copied_text(self):
        lines = []
        with open(self.FILENAME) as f:
            csv_reader = csv.reader(f)
            [lines.append(row[0]) for row in csv_reader]

        return lines

    def create_preview_modal(self) -> Adw.MessageDialog:
        lines = self.get_copied_text()

        listbox = Gtk.ListBox(css_classes=['boxed-list'], width_request=300)

        for l in lines:
            preview_text = l[:25]
            preview_text = preview_text.replace('\n', '')
            buffer = Gtk.TextBuffer(text=l)
            textview = Gtk.TextView(buffer=buffer, editable=False, 
                                    css_classes=['clipboard-dialog-textview'])

            if len(l) > 26:
                preview_text = preview_text + '...'

            copy_btn = Gtk.Button(
                icon_name='copy-symbolic',
                css_classes=['flat'],
                valign=Gtk.Align.CENTER
            )

            copy_btn.connect('clicked', self.on_copy_btn_clicked, l)

            actionrow = Adw.ExpanderRow(
                title=preview_text,
            )

            actionrow.add_row(
                textview
            )

            actionrow.add_suffix(copy_btn)

            listbox.append(actionrow)


        dialog = Adw.MessageDialog(
            extra_child=listbox
        )

        dialog.add_response('close', _('Close'))
        dialog.set_close_response('close')

        return dialog