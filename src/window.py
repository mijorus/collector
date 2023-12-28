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
import subprocess

gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Adw, Gio, Gdk, GObject, GLib

from .lib.utils import get_giofile_content_type
from .lib.DroppedItem import DroppedItem, DroppedItemNotSupportedException

class CollectorWindow(Adw.ApplicationWindow):

    DEFAULT_DROP_ICON_NAME = 'go-jump-symbolic'
    EMPTY_DROP_TEXT = _('Drop content here')
    CAROUSEL_ICONS_PIX_SIZE=50

    def __init__(self, **kwargs):
        super().__init__(**kwargs, title='CollectorMainWindow')

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

        self.icon_carousel = Adw.Carousel(spacing=15, allow_mouse_drag=False)
        carousel_indicator = Adw.CarouselIndicatorDots(carousel=self.icon_carousel)
        self.default_drop_icon = Gtk.Image(icon_name='go-jump-symbolic', pixel_size=self.CAROUSEL_ICONS_PIX_SIZE)
        self.release_drop_icon = Gtk.Image(icon_name='arrow2-down-symbolic', pixel_size=self.CAROUSEL_ICONS_PIX_SIZE)
        self.release_drag_icon = Gtk.Image(icon_name='arrow2-up-symbolic', pixel_size=self.CAROUSEL_ICONS_PIX_SIZE)

        self.carousel_container.append(self.icon_carousel)
        self.carousel_container.append(carousel_indicator)

        self.icon_stack.add_child(self.carousel_container)
        self.icon_stack.add_child(self.default_drop_icon)
        self.icon_stack.add_child(self.release_drop_icon)
        self.icon_stack.add_child(self.release_drag_icon)
        self.icon_stack.set_visible_child(self.default_drop_icon)

        content.append(self.icon_stack)

        label_stack = Adw.ViewStack()
        self.drops_label = Gtk.Label(label=self.EMPTY_DROP_TEXT, css_classes=['dim-label'])

        label_stack.add(self.drops_label)

        content.append(label_stack)

        # toolbar = Adw.ToolbarView()
        # toolbar.add_top_bar(header_bar)
        # toolbar.set_content(content)

        overlay = Gtk.Overlay(child=content)
        overlay.add_overlay(header_bar)
        overlay.set_clip_overlay(header_bar, True)

        drag_source_controller = Gtk.DragSource()
        drag_source_controller.connect('prepare', self.on_drag_prepare)
        drag_source_controller.connect('drag-end', self.on_drag_end)
        drag_source_controller.connect('drag-begin', self.on_drag_start)

        self.is_dragging_away = False
        drop_target_controller = Gtk.DropTarget(actions=Gdk.DragAction.COPY)
        drop_target_controller.set_gtypes([Gio.File, GObject.TYPE_STRING])
        drop_target_controller.connect('drop', self.on_drop_event)
        drop_target_controller.connect('enter', self.on_drop_enter)
        drop_target_controller.connect('leave', self.on_drop_leave)

        event_controller_key = Gtk.EventControllerKey()
        event_controller_key.connect('key-pressed', self.on_key_pressed)

        self.add_controller(drop_target_controller)
        self.add_controller(event_controller_key)
        content.add_controller(drag_source_controller)

        self.dropped_items: list[DroppedItem] = []
        self.set_default_size(200, 200)
        self.set_resizable(False)
        self.set_content(overlay)

        self.init_cache_folder()


    def init_cache_folder(self):
        drops_cache_path = GLib.get_user_cache_dir() + f'/drops'
        if os.path.exists(drops_cache_path):
            shutil.rmtree(drops_cache_path)

        os.mkdir(drops_cache_path)

    def on_drag_prepare(self, source, x, y):
        if not self.dropped_items:
            return None

        dropped_files = [f.item for f in self.dropped_items]
        path_list = '\n'.join([f.target_path for f in self.dropped_items])
        uri_list = '\n'.join([f'file://{f.target_path}' for f in self.dropped_items])

        return Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_value(dropped_files[0]),
            Gdk.ContentProvider.new_for_value(path_list),
            Gdk.ContentProvider.new_for_value(uri_list),
            Gdk.ContentProvider.new_for_bytes(
                'text/uri-list', 
                GLib.Bytes.new(uri_list.encode())
            )
        ])

    def on_drag_end(self, source, drag, move_data):
        self.is_dragging_away = False
        self.drops_label.set_label(_('Release to drop'))
        self.on_drop_leave(None)

    def on_drag_start(self, drag, move_data):
        self.is_dragging_away = True
        self.icon_stack.set_visible_child(self.release_drag_icon)

    def on_drop_event(self, widget, value, x, y):
        if self.is_dragging_away:
            return False

        try:
            dropped_item = DroppedItem(value)
        except DroppedItemNotSupportedException:
            return False

        new_dropped_icon = dropped_item.preview_image

        self.dropped_items.append(dropped_item)
        self.icon_carousel.append(new_dropped_icon)
        self.icon_carousel.scroll_to(new_dropped_icon, True)
        self.icon_stack.set_visible_child(self.carousel_container)

        self.on_drop_leave(widget)
        return True

    def on_drop_enter(self, widget, x, y):
        if not self.is_dragging_away:
            self.icon_stack.set_visible_child(self.release_drop_icon)
            self.drops_label.set_label(_('Release to collect'))

        return Gdk.DragAction.COPY

    def on_drop_leave(self, widget):
        if not self.is_dragging_away:
            if self.dropped_items:
                self.icon_stack.set_visible_child(self.carousel_container)
                tot_size = sum([d.size for d in self.dropped_items])

                if tot_size > (1024 * 1024 * 1024):
                    tot_size = f'{round(tot_size / (1024 * 1024 * 1024), 1)} GB'
                elif tot_size > (1024 * 1024):
                    tot_size = f'{round(tot_size / (1024 * 1024), 1)} MB'
                else:
                    tot_size = f'{round(tot_size / (1024), 1)} KB'

                if len(self.dropped_items) == 1:
                    self.drops_label.set_label(_('1 File | {size}').format(size=tot_size))
                else:
                    self.drops_label.set_label(_('{files_count} Files | {size}').format(
                        files_count=len(self.dropped_items),
                        size=tot_size
                    ))
            else:
                self.drops_label.set_label(self.EMPTY_DROP_TEXT)
                self.icon_stack.set_visible_child(self.default_drop_icon)

    def on_key_pressed(self, widget, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self.close()
