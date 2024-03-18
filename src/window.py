# window.py
#
# Copyright 2023 lorenzo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import gi
import shutil
import logging
import threading
from typing import Optional

from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib

from .lib.constants import APP_ID, SUPPORTED_IMG_TYPES
from .lib.CarouselItem import CarouselItem
from .lib.CsvCollector import CsvCollector
from .lib.utils import get_gsettings
from .lib.DroppedItem import DroppedItem, DroppedItemNotSupportedException

class CollectorWindow(Adw.ApplicationWindow):

    
    COLLECTOR_COLORS = ["blue", "yellow", "purple", "rose", "orange", "green"]
    EMPTY_DROP_TEXT = _('Drop Content Here')
    CAROUSEL_ICONS_PIX_SIZE=50
    DROPS_BASE_PATH = GLib.get_user_cache_dir() + f'/drops'
    settings = get_gsettings()

    def __init__(self, window_index=0, **kwargs):
        super().__init__(**kwargs, title='CollectorMainWindow')
        self.DROPS_PATH = f'{self.DROPS_BASE_PATH}/{window_index}'

        self.settings.connect('changed::keep-on-drag', self.on_keep_on_drag_changed)

        self.WINDOW_INDEX = window_index
        self.window_color = self.get_color()
        self.clipboard = Gdk.Display.get_default().get_clipboard()
        self.window_color_btn: Optional[Gtk.Button] = None
        self.csvcollector: Optional[CsvCollector] = None

        header_bar = self.create_header_bar()
        bottom_bar = self.create_bottom_bar()

        content_box = self.create_content_box()

        self.icon_stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.carousel_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        carousel_info_btn = Gtk.Button(
            css_classes=['circular', 'opaque', 'dropped-item-info-btn'],
            icon_name='view-more-symbolic',
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )

        carousel_info_btn.connect('clicked', self.on_carousel_info_btn)
        self.icon_carousel = Adw.Carousel(spacing=15, allow_mouse_drag=False)
        carousel_indicator = Adw.CarouselIndicatorDots(carousel=self.icon_carousel)
        self.default_drop_icon = Gtk.Image(icon_name='go-jump-symbolic', pixel_size=self.CAROUSEL_ICONS_PIX_SIZE)
        self.release_drop_icon = Gtk.Image(icon_name='arrow2-down-symbolic', pixel_size=self.CAROUSEL_ICONS_PIX_SIZE)
        self.release_drag_icon = Gtk.Image(icon_name='arrow2-up-symbolic', pixel_size=self.CAROUSEL_ICONS_PIX_SIZE)

        carousel_overlay = Gtk.Overlay(child=self.icon_carousel)
        carousel_overlay.add_overlay(carousel_info_btn)

        self.carousel_popover = Gtk.Popover(child=self.create_carousel_popover_content())
        carousel_overlay.add_overlay(self.carousel_popover)

        self.carousel_container.append(carousel_overlay)
        self.carousel_container.append(carousel_indicator)

        [self.icon_stack.add_child(w) for w in [self.carousel_container, 
            self.default_drop_icon, self.release_drop_icon, self.release_drag_icon]]

        self.icon_stack.set_visible_child(self.default_drop_icon)

        content_box.append(self.icon_stack)

        label_stack = Adw.ViewStack()
        self.drops_label = Gtk.Label(
            justify=Gtk.Justification.CENTER,
            label=self.EMPTY_DROP_TEXT, 
            css_classes=['dim-label']
        )

        label_stack.add(self.drops_label)

        self.keep_items_indicator = Gtk.Revealer(
            reveal_child=(self.settings.get_boolean('keep-on-drag')),
            transition_type=Gtk.RevealerTransitionType.CROSSFADE,
            child=Gtk.Button(
                icon_name='padlock2-symbolic',
                css_classes=['flat'],
                sensitive=False
            )
        )

        content_box.append(label_stack)
        bottom_bar.pack_end(self.keep_items_indicator)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header_bar)
        toolbar.add_bottom_bar(bottom_bar)
        toolbar.set_content(content_box)

        # overlay = Gtk.Overlay(child=content)
        # overlay.add_overlay(header_bar)
        # overlay.set_clip_overlay(header_bar, True)

        self.drag_source_controller = self.create_drag_source_controller()
        self.is_dragging_away = False
        self.drag_aborted = False

        drop_target_controller = self.create_drop_target_controller()

        event_controller_key = self.create_event_controller_key()

        self.add_controller(drop_target_controller)
        self.add_controller(event_controller_key)
        content_box.add_controller(self.drag_source_controller)

        self.dropped_items: list[CarouselItem] = []
        self.set_default_size(225, 225)
        self.set_resizable(False)
        self.set_content(toolbar)

        self.connect('close-request', self.on_close_request)
        self.init_cache_folder()

    def get_color(self):
        return self.COLLECTOR_COLORS[(self.WINDOW_INDEX % len(self.COLLECTOR_COLORS))]

    def init_cache_folder(self):
        if os.path.exists(self.DROPS_PATH):
            logging.debug('Removing ' +  self.DROPS_PATH)
            shutil.rmtree(self.DROPS_PATH)

        logging.debug('Creting empty folder for drops at: ' +  self.DROPS_PATH)

        if not os.path.exists(self.DROPS_BASE_PATH):
            os.mkdir(self.DROPS_BASE_PATH)

        os.mkdir(self.DROPS_PATH)

    def on_keep_on_drag_changed(self, settings, key):
        val = settings.get_boolean(key)
        self.keep_items_indicator.set_reveal_child(val)

    def on_drag_prepare(self, source, x, y):
        if not self.dropped_items:
            return None

        uri_list = '\n'.join([f'file://{f.dropped_item.target_path}' for f in self.dropped_items])
        return Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_bytes(
                'text/uri-list', 
                GLib.Bytes.new(uri_list.encode())
            )
        ])

    def on_drag_cancel(self, source, drag, reason):
        logging.debug('Drag operation canceled, reason: ', reason)
        self.drag_aborted = True

    def on_drag_end(self, source, drag, move_data):
        self.is_dragging_away = False

        if not self.drag_aborted:
            if self.keep_items_indicator.get_child_visible():
               self.remove_all_items()

        self.drag_aborted = False
        self.on_drop_leave(None)

    def on_drag_start(self, drag, move_data):
        self.is_dragging_away = True
        
        self.drops_label.set_label(_('Release to drop'))
        self.icon_stack.set_visible_child(self.release_drag_icon)

    def on_drop_event(self, widget, value, x, y):
        if self.is_dragging_away:
            return False
        
        self.drop_value(value)
        self.on_drop_leave(widget)

        return True
    
    def on_drop_event_complete(self, carousel_items: list[CarouselItem]):
        new_image = False
        for carousel_item in carousel_items:
            dropped_item = carousel_item.dropped_item
            self.icon_carousel.remove(carousel_item.image)
            
            for i, c in enumerate(self.dropped_items):
                if c is carousel_item:
                    del self.dropped_items[i]
                    break

            if self.settings.get_boolean('collect-text-to-csv') and \
                    dropped_item.content_is_text:

                value = dropped_item.get_text_content()
                if self.csvcollector:
                    self.csvcollector.append_text(value)
                else:
                    self.csvcollector = CsvCollector(self.DROPS_PATH)
                    self.csvcollector.append_text(value)

                    dropped_item = DroppedItem(self.csvcollector.get_gfile(),
                        is_clipboard=True,
                        drops_dir=self.DROPS_PATH,
                        dynamic_size=True)
                    
                    carousel_item = CarouselItem(
                        item=dropped_item, 
                        image=self.get_new_image_from_dropped_item(dropped_item),
                        index=0
                    )

                    self.icon_carousel.prepend(carousel_item.image)
                    self.dropped_items.insert(0, carousel_item)
            else:
                new_image = self.get_new_image_from_dropped_item(dropped_item)
                new_image.set_tooltip_text(dropped_item.display_value)

                carousel_item.image = new_image

                self.icon_carousel.append(new_image)          
                self.dropped_items.append(carousel_item)  
                self.dropped_items[carousel_item.index] = carousel_item

        if new_image:
            self.icon_carousel.scroll_to(new_image, True)

        self.update_tot_size_sum()

    def on_drop_event_complete_async(self, carousel_items: list[CarouselItem]):
        async_items: list[CarouselItem] = []
        GLib.idle_add(lambda: self.update_tot_size_sum(True))

        for carousel_item in carousel_items:
            if carousel_item.dropped_item.async_load:
                async_items.append(carousel_item)

        async_opts: list[threading.Thread] = []

        for item in async_items:
            t = threading.Thread(target=item.dropped_item.complete_load)
            async_opts.append(t)

        [t.start() for t in async_opts]
        [t.join() for t in async_opts]

        logging.debug('Loading async items terminated')
        GLib.idle_add(lambda: self.on_drop_event_complete(async_items))

    def on_drop_enter(self, widget, x, y):
        if not self.is_dragging_away:
            self.icon_stack.set_visible_child(self.release_drop_icon)
            self.drops_label.set_label(_('Release to Collect'))

        return Gdk.DragAction.COPY

    def on_drop_leave(self, widget=None):
        if self.is_dragging_away:
            self.drag_aborted = True
        else:
            if self.dropped_items:
                self.icon_stack.set_visible_child(self.carousel_container)
                self.update_tot_size_sum()
            else:
                self.reset_to_empty_state()

    def on_key_pressed(self, widget, keyval, keycode, state):
        ctrl_key = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift_key = bool(state & Gdk.ModifierType.SHIFT_MASK)
        alt_key = bool(state & Gdk.ModifierType.ALT_MASK)
    
        if keyval == Gdk.KEY_Escape:
            if self.is_dragging_away:
                self.drag_aborted = True
                self.drag_source_controller.drag_cancel()
                return True
            else:
                self.close()
                return True
        elif keyval == Gdk.KEY_d:
            if ctrl_key and self.settings.get_boolean('keep-on-drag') == False:
                r = self.keep_items_indicator.get_reveal_child()
                self.keep_items_indicator.set_reveal_child(not r)
        elif keyval == Gdk.KEY_v:
            if ctrl_key and not self.is_dragging_away:
                cp_read_type = None
                cp_is_text = 'text/plain' in self.clipboard.get_formats().get_mime_types()

                gtypes = self.clipboard.get_formats()
                supported_types = [Gdk.FileList]

                for t in supported_types:
                    if gtypes.contain_gtype(t):
                        cp_read_type = t
                        break

                if cp_read_type:
                    logging.debug(f'Selected type from clipboard: {cp_read_type}')
                    self.clipboard.read_value_async(cp_read_type, 1, None, 
                        callback=self.clipboard_read_async_end)
                elif cp_is_text:
                    logging.debug('Reading text from clipboard')
                    self.clipboard.read_text_async(None, 
                        callback=self.clipboard_read_text_async_end)
                
                return True
        elif keyval == Gdk.KEY_BackSpace:
            if self.dropped_items and not self.is_dragging_away:
                self.delete_focused_item()
                return True
        elif keyval == Gdk.KEY_Left:
            self.scroll_in_direction(0)
            return True
        elif keyval == Gdk.KEY_Right:
            self.scroll_in_direction(1)
            return True
        elif keyval == Gdk.KEY_Menu:
            if self.dropped_items:
                self.carousel_popover.popup()
            return True
        elif keyval == Gdk.KEY_o:
            if self.dropped_items and ctrl_key:
                self.on_preview_btn_clicked(None)
                return True
        elif keyval == Gdk.KEY_Delete:
            if self.dropped_items and not self.is_dragging_away:
                self.remove_all_items()
                self.carousel_popover.popdown()
                return True

        return False
    
    def scroll_in_direction(self, direction):
        """
            0: scroll left
            1: scroll right
        """

        if not self.dropped_items:
            return

        i = int(self.icon_carousel.get_position())

        if (i == 0 and direction == 0) or \
            i == (len(self.dropped_items) - 1) and direction == 1:
            return

        i = i - 1 if direction == 0 else i + 1
        self.icon_carousel.scroll_to(self.dropped_items[i].image, True)

    def drop_value(self, value):
        dropped_items = []
        carousel_items = []
    
        try:
            if isinstance(value, Gdk.FileList):
                for file in value.get_files():
                    d = DroppedItem(file, drops_dir=self.DROPS_PATH)
                    dropped_items.append(d)
            elif isinstance(value, str) and self.settings.get_boolean('collect-text-to-csv'):
                dropped_item = DroppedItem(value, drops_dir=self.DROPS_PATH)

                if dropped_item.async_load:
                    dropped_items.append(dropped_item)
                else:
                    if self.csvcollector:
                        self.csvcollector.append_text(value)

                        for c in self.dropped_items:
                            if c.dropped_item.is_clipboard:
                               self.icon_carousel.scroll_to(c.image, True)
                               break

                        self.update_tot_size_sum()
                        return

                    else:
                        self.csvcollector = CsvCollector(self.DROPS_PATH)
                        self.csvcollector.append_text(value)

                        dropped_item = DroppedItem(self.csvcollector.get_gfile(),
                            is_clipboard=True,
                            drops_dir=self.DROPS_PATH,
                            dynamic_size=True)
                        
                        dropped_items.append(dropped_item)

            else:
                dropped_item = DroppedItem(value, drops_dir=self.DROPS_PATH)
                dropped_items.append(dropped_item)
        except DroppedItemNotSupportedException as e:
            logging.warn(f'Invalid data type: {e.item}')
            return False
        except Exception as e:
            logging.error(f'Item not supported: {e}')
            return False

        new_image = None
        for dropped_item in dropped_items:
            if dropped_item.async_load:
                loader = Gtk.Spinner(spinning=True, hexpand=False, vexpand=False)
                carousel_item = CarouselItem(
                    item=dropped_item, 
                    image=loader,
                    index=len(self.dropped_items)
                )

                carousel_items.append(carousel_item)
                self.icon_carousel.append(loader)
            else:
                new_image = self.get_new_image_from_dropped_item(dropped_item)
                new_image.set_tooltip_text(dropped_item.display_value)
                
                carousel_item = CarouselItem(
                    item=dropped_item, 
                    image=new_image,
                    index=0 if dropped_item.is_clipboard else len(self.dropped_items)
                )

                carousel_items.append(carousel_item)
                if dropped_item.is_clipboard:
                    self.icon_carousel.prepend(new_image)
                else:
                    self.icon_carousel.append(new_image)

        for c in carousel_items:
            if c.dropped_item.is_clipboard:
                self.dropped_items.insert(0, c)
            else:
                self.dropped_items.append(c)

        if any([d.async_load for d in dropped_items]):
            threading.Thread(
                target=self.on_drop_event_complete_async, 
                args=(carousel_items,)
            ).start()

        self.icon_stack.set_visible_child(self.carousel_container)

        if new_image:
            self.icon_carousel.scroll_to(new_image, True)

    def on_key_released(self, widget, keyval, keycode, state):
        # ctrl_key = bool(state & Gdk.ModifierType.CONTROL_MASK)
        # shift_key = bool(state & Gdk.ModifierType.SHIFT_MASK)
        # alt_key = bool(state & Gdk.ModifierType.ALT_MASK)

        return False

    def on_carousel_info_btn(self, widget: Gtk.Button):
        self.carousel_popover.popup()

    def delete_focused_item(self, widget=None):
        i = int(self.icon_carousel.get_position())
        item = self.dropped_items[i]
        
        if len(self.dropped_items) == 1:
            self.remove_all_items()
        else:
            if self.csvcollector and item.dropped_item.is_clipboard:
                self.csvcollector.clear()
                self.csvcollector = None

            self.icon_carousel.remove(item.image)
            self.dropped_items.pop(i)
            self.on_drop_leave(None)

            self.update_tot_size_sum()

        self.carousel_popover.popdown()

    def on_preview_btn_clicked(self, btn=None):
        i = int(self.icon_carousel.get_position())
        item = self.dropped_items[i].dropped_item
        file = item.gfile

        if item.is_clipboard:
            m = self.csvcollector.create_preview_modal()
            m.set_transient_for(self)
            m.present()
        else:
            launcher = Gtk.FileLauncher.new(file)
            launcher.launch(self, None, None, None)

    def on_copy_btn_clicked(self, btn=None):
        i = int(self.icon_carousel.get_position())
        carousel_item = self.dropped_items[i]

        if carousel_item.dropped_item.is_clipboard:
            content = self.csvcollector.get_copied_text()
            content_prov = Gdk.ContentProvider.new_for_value('\n'.join(content))
        elif carousel_item.dropped_item.content_is_text:
            content = carousel_item.dropped_item.get_text_content()
            content_prov = Gdk.ContentProvider.new_for_value(content)
        else:
            gfile = carousel_item.dropped_item.gfile
            content_prov = Gdk.ContentProvider.new_union([
                Gdk.ContentProvider.new_for_value(gfile),
                Gdk.ContentProvider.new_for_bytes(
                    'text/uri-list', 
                    GLib.Bytes.new(gfile.get_uri().encode())
                )
            ])

        self.clipboard.set_content(content_prov)
        self.carousel_popover.popdown()

    def update_tot_size_sum(self, loading_state=False):
        if loading_state:
            self.drops_label.set_label('...')
            return

        tot_size = sum([d.dropped_item.get_size() for d in self.dropped_items])

        if tot_size > (1024 * 1024 * 1024):
            tot_size = f'{round(tot_size / (1024 * 1024 * 1024), 1)} GB'
        elif tot_size > (1024 * 1024):
            tot_size = f'{round(tot_size / (1024 * 1024), 1)} MB'
        elif tot_size > 1014:
            tot_size = f'{round(tot_size / (1024), 1)} KB'
        else:
            tot_size = f'{round(tot_size)} Byte'

        if len(self.dropped_items) == 1:
            self.drops_label.set_label(_('1 File | {size}').format(size=tot_size))
        else:
            self.drops_label.set_label(_('{files_count} Files | {size}').format(
                files_count=len(self.dropped_items),
                size=tot_size
            ))

    def remove_all_items(self):
        for d in self.dropped_items:
            self.icon_carousel.remove(d.image)

        if self.csvcollector:
            self.csvcollector.clear()
            self.csvcollector = None

        self.dropped_items = []
        self.update_tot_size_sum()
        self.reset_to_empty_state()

    def reset_to_empty_state(self):
        self.drops_label.set_label(self.EMPTY_DROP_TEXT)
        self.icon_stack.set_visible_child(self.default_drop_icon)

    def on_close_request(self, widget):
        if os.path.exists(self.DROPS_PATH):
            logging.debug('Removing ' +  self.DROPS_PATH)
            shutil.rmtree(self.DROPS_PATH)

        return False
    
    def get_new_image_from_dropped_item(self, dropped_item: DroppedItem):
        new_image = None
        if isinstance(dropped_item.preview_image, str):
            new_image = Gtk.Image(icon_name=dropped_item.preview_image, pixel_size=70)
        elif isinstance(dropped_item.preview_image, Gio.Icon):
            new_image = Gtk.Image(gicon=dropped_item.preview_image, pixel_size=70)
        elif isinstance(dropped_item.preview_image, Gio.File):
            new_image = Gtk.Image(
                file=dropped_item.preview_image.get_path(),
                overflow=Gtk.Overflow.HIDDEN,
                css_classes=['dropped-item-thumb'],
                height_request=70,
                width_request=70,
            )

        return new_image
    
    def clipboard_read_async_end(self, source, res):
        result = self.clipboard.read_value_finish(res)
        logging.debug(f'Received clipboard content {result}')

        drop_value = False

        # if isinstance(result, Gdk.Texture):
        #     drop_value = self.create_tmp_file_from_texture(result)

        if isinstance(result, Gio.File) or isinstance(result, Gdk.FileList) \
                or isinstance(result, Gdk.Texture):
            drop_value = result

        if drop_value:
            self.drop_value(drop_value)
            self.on_drop_leave()

    def clipboard_read_text_async_end(self, source, res):
        result = self.clipboard.read_text_finish(res)
        self.drop_value(result)
        self.on_drop_leave()

    def set_window_color(self, color):
        old_color = self.window_color
        self.window_color = color

        if self.window_color_btn:
            self.window_color_btn.remove_css_class(f'collector-{old_color}')
            self.window_color_btn.add_css_class(f'collector-{color}')
        
    def create_drag_source_controller(self):
        drag_source_controller = Gtk.DragSource()
        drag_source_controller.connect('prepare', self.on_drag_prepare)
        drag_source_controller.connect('drag-end', self.on_drag_end)
        drag_source_controller.connect('drag-cancel', self.on_drag_cancel)
        drag_source_controller.connect('drag-begin', self.on_drag_start)

        return drag_source_controller

    def create_drop_target_controller(self):
        drop_target_controller = Gtk.DropTarget(actions=Gdk.DragAction.COPY)
        drop_target_controller.set_gtypes([Gdk.Texture, Gdk.FileList, GObject.TYPE_STRING])
        drop_target_controller.connect('drop', self.on_drop_event)
        drop_target_controller.connect('enter', self.on_drop_enter)
        drop_target_controller.connect('leave', self.on_drop_leave)
        return drop_target_controller
    
    def create_event_controller_key(self):
        event_controller_key = Gtk.EventControllerKey()
        event_controller_key.connect('key-pressed', self.on_key_pressed)
        event_controller_key.connect('key-released', self.on_key_released)
        return event_controller_key
    
    def create_content_box(self):
        content_box = Gtk.Box(
            css_classes=['droparea-target'],
            margin_top=15,
            margin_end=5,
            margin_start=5,
            spacing=10,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            vexpand=True,
        )
        
        return content_box

    def create_header_bar(self):
        menu_obj = Gtk.Builder.new_from_resource('/it/mijorus/collector/gtk/main-menu.ui')
        menu_button = Gtk.MenuButton(icon_name='open-menu', menu_model=menu_obj.get_object('primary_menu'))
    
        header_bar = Adw.HeaderBar(
            show_title=False,
            decoration_layout='icon:close',
            valign=Gtk.Align.START,
            css_classes=['flat']
        )
        
        header_bar.pack_start(menu_button)

        return header_bar
    
    def create_bottom_bar(self):
        bottom_bar = Gtk.ActionBar()

        self.window_color_btn = Gtk.MenuButton(
            icon_name='big-dot-symbolic',
            css_classes=['flat', 'circular', f'collector-{self.window_color}']
        )

        color_list = Gtk.FlowBox(
            homogeneous=True,
            min_children_per_line=len(self.COLLECTOR_COLORS),
            max_children_per_line=len(self.COLLECTOR_COLORS)
        )

        for c in self.COLLECTOR_COLORS:
            b = Gtk.Image(
                icon_name='big-dot-symbolic',
                css_classes=[f'collector-{c}', 'collector-color-image']
            )

            r = Gtk.FlowBoxChild(child=b)
            r.__color = c
            color_list.append(r)

            if c == self.window_color:
                color_list.select_child(r)

        color_list.connect('child-activated',
                           lambda w, c: self.set_window_color(c.__color))
        
        color_popover = Gtk.Popover(child=color_list)
        self.window_color_btn.set_popover(color_popover)

        bottom_bar.pack_start(self.window_color_btn)
        return bottom_bar

    def create_carousel_popover_content(self):
        carousel_popover_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        copy_btn = Gtk.Button(icon_name='copy-symbolic')
        copy_btn.connect('clicked', self.on_copy_btn_clicked)

        preview_btn = Gtk.Button(icon_name='eye-open-negative-filled-symbolic')
        preview_btn.connect('clicked', self.on_preview_btn_clicked)

        delete_btn = Gtk.Button(icon_name='user-trash-symbolic', css_classes=['error'])
        delete_btn.connect('clicked', self.delete_focused_item)

        [carousel_popover_content.append(b) for b in [
            copy_btn, preview_btn, delete_btn
        ]]

        return carousel_popover_content
