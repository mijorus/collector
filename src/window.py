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

from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib

from .lib.constants import *
from .lib.CarouselItem import CarouselItem
from .lib.utils import get_giofile_content_type
from .lib.DroppedItem import DroppedItem, DroppedItemNotSupportedException

class CollectorWindow(Adw.ApplicationWindow):

    EMPTY_DROP_TEXT = _('Drop content here')
    CAROUSEL_ICONS_PIX_SIZE=50

    def __init__(self, **kwargs):
        super().__init__(**kwargs, title='CollectorMainWindow')

        self.settings = Gio.Settings.new(APP_ID)

        header_bar = Adw.HeaderBar(
            show_title=False,
            decoration_layout='icon:close',
            valign=Gtk.Align.START,
            css_classes=['flat']
        )

        content = Gtk.Box(
            css_classes=['droparea-target'],
            margin_top=20,
            margin_end=5,
            margin_start=5,
            spacing=10,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.CENTER,
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            vexpand=True,
        )

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

        
        self.carousel_popover = Gtk.Popover(child=self.get_carousel_popover_content())
        carousel_overlay.add_overlay(self.carousel_popover)

        self.carousel_container.append(carousel_overlay)
        self.carousel_container.append(carousel_indicator)

        self.icon_stack.add_child(self.carousel_container)
        self.icon_stack.add_child(self.default_drop_icon)
        self.icon_stack.add_child(self.release_drop_icon)
        self.icon_stack.add_child(self.release_drag_icon)
        self.icon_stack.set_visible_child(self.default_drop_icon)

        content.append(self.icon_stack)

        label_stack = Adw.ViewStack()
        self.drops_label = Gtk.Label(
            justify=Gtk.Justification.CENTER,
            label=self.EMPTY_DROP_TEXT, 
            css_classes=['dim-label']
        )

        label_stack.add(self.drops_label)

        content.append(label_stack)

        # toolbar = Adw.ToolbarView()
        # toolbar.add_top_bar(header_bar)
        # toolbar.set_content(content)

        overlay = Gtk.Overlay(child=content)
        overlay.add_overlay(header_bar)
        overlay.set_clip_overlay(header_bar, True)

        self.drag_source_controller = Gtk.DragSource()
        self.drag_source_controller.connect('prepare', self.on_drag_prepare)
        self.drag_source_controller.connect('drag-end', self.on_drag_end)
        self.drag_source_controller.connect('drag-cancel', self.on_drag_cancel)
        self.drag_source_controller.connect('drag-begin', self.on_drag_start)

        self.is_dragging_away = False
        self.drag_aborted = False

        drop_target_controller = Gtk.DropTarget(actions=Gdk.DragAction.COPY)
        drop_target_controller.set_gtypes([Gio.File, GObject.TYPE_STRING])
        drop_target_controller.connect('drop', self.on_drop_event)
        drop_target_controller.connect('enter', self.on_drop_enter)
        drop_target_controller.connect('leave', self.on_drop_leave)

        event_controller_key = Gtk.EventControllerKey()
        event_controller_key.connect('key-pressed', self.on_key_pressed)

        self.add_controller(drop_target_controller)
        self.add_controller(event_controller_key)
        content.add_controller(self.drag_source_controller)

        self.dropped_items: list[CarouselItem] = []
        self.set_default_size(200, 200)
        self.set_resizable(False)
        self.set_content(overlay)

        self.init_cache_folder()

    def init_cache_folder(self):
        drops_cache_path = GLib.get_user_cache_dir() + f'/drops'
        if os.path.exists(drops_cache_path):
            shutil.rmtree(drops_cache_path)

        os.mkdir(drops_cache_path)

    def get_carousel_popover_content(self):
        carousel_popover_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        carousel_popover_content.append(
            Gtk.Button(icon_name='info-symbolic')
        )

        preview_btn = Gtk.Button(icon_name='eye-open-negative-filled-symbolic')
        preview_btn.connect('clicked', self.on_preview_btn_clicked)
        carousel_popover_content.append(
            preview_btn
        )

        delete_btn = Gtk.Button(icon_name='user-trash-symbolic', css_classes=['error'])
        delete_btn.connect('clicked', self.delete_focused_item)
        carousel_popover_content.append(
            delete_btn
        )

        return carousel_popover_content

    def on_drag_prepare(self, source, x, y):
        if not self.dropped_items:
            return None

        dropped_files = [f.dropped_item.gfile for f in self.dropped_items]
        # path_list = '\n'.join([f.target_path for f in self.dropped_items])
        # uri_list = '\n'.join([f'file://{f.target_path}' for f in self.dropped_items])

        return Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_array(dropped_files)),
            # Gdk.ContentProvider.new_for_value(path_list),
            # Gdk.ContentProvider.new_for_value(uri_list),
            # Gdk.ContentProvider.new_for_bytes(
            #     'text/uri-list', 
            #     GLib.Bytes.new(uri_list.encode())
            # )
        ])

    def on_drag_cancel(self, source, drag, reason):
        pass

    def on_drag_end(self, source, drag, move_data):
        self.is_dragging_away = False

        if not self.drag_aborted:
            if self.settings.get_boolean('clear-on-drag'):
               self.remove_all_items()

        self.drag_aborted = False
        self.on_drop_leave(None)

    def on_drag_start(self, drag, move_data):
        self.is_dragging_away = True
        
        self.drops_label.set_label(_('Release to drop\nPress Esc to cancel drag'))
        self.icon_stack.set_visible_child(self.release_drag_icon)

    def on_drop_event(self, widget, value, x, y):
        if self.is_dragging_away:
            return False
        
        print(value)

        try: 
            dropped_item = DroppedItem(value)
        except DroppedItemNotSupportedException:
            return False

        if isinstance(dropped_item.preview_image, str):
            new_image = Gtk.Image(icon_name=dropped_item.preview_image, pixel_size=70)
        else:
            new_image = Gtk.Image(gicon=dropped_item.preview_image, pixel_size=70)

        carousel_item = CarouselItem(item=dropped_item, image=new_image)

        self.dropped_items.append(carousel_item)
        self.icon_carousel.append(new_image)
        self.icon_carousel.scroll_to(new_image, True)
        self.icon_stack.set_visible_child(self.carousel_container)

        self.on_drop_leave(widget)
        return True

    def on_drop_enter(self, widget, x, y):
        if not self.is_dragging_away:
            self.icon_stack.set_visible_child(self.release_drop_icon)
            self.drops_label.set_label(_('Release to collect'))

        return Gdk.DragAction.COPY

    def on_drop_leave(self, widget=None):
        if self.is_dragging_away:
            self.drag_aborted = True
        else:
            if self.dropped_items:
                self.icon_stack.set_visible_child(self.carousel_container)
                self.update_tot_size_sum()
            else:
                self.drops_label.set_label(self.EMPTY_DROP_TEXT)
                self.icon_stack.set_visible_child(self.default_drop_icon)

    def on_key_pressed(self, widget, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            if self.is_dragging_away:
                self.drag_aborted = True
                self.drag_source_controller.drag_cancel()
                return True
            else:
                self.close()
                return True
        elif keyval == Gdk.KEY_Control_L:
            if self.is_dragging_away:
                pass
        elif keyval == Gdk.KEY_BackSpace:
            if self.dropped_items and not self.is_dragging_away:
                self.remove_all_items()
                self.carousel_popover.popdown()
        
        return False

    def on_carousel_info_btn(self, widget: Gtk.Button):
        self.carousel_popover.popup()

    def delete_focused_item(self, widget):
        i = int(self.icon_carousel.get_position())
        
        self.icon_carousel.remove(self.dropped_items[i].image)
        self.dropped_items.pop(i)
        self.on_drop_leave(None)

        self.update_tot_size_sum()

        self.carousel_popover.popdown()

    def on_preview_btn_clicked(self, btn: Gtk.Button):
        i = int(self.icon_carousel.get_position())
        file = self.dropped_items[i].dropped_item.gfile

        launcher = Gtk.FileLauncher.new(file)
        launcher.launch(self, None, None, None)

    def update_tot_size_sum(self):
        tot_size = sum([d.dropped_item.size for d in self.dropped_items])

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

        self.dropped_items = []
        self.update_tot_size_sum()
