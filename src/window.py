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

from gi.repository import Gtk, Adw, Gio, Gdk, GObject

from .lib.DroppedItem import DroppedItem

class CollectorWindow(Adw.ApplicationWindow):

    DEFAULT_DROP_ICON_NAME = 'go-jump-symbolic'
    EMPTY_DROP_TEXT = _('Drop content here')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        header_bar = Adw.HeaderBar(
            show_title=False,
            decoration_layout='icon:close',
            valign=Gtk.Align.START,
            css_classes=['flat']
        )

        content = Gtk.Box(
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

        self.icon_stack = Adw.ViewStack()
        self.carousel_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.icon_carousel = Adw.Carousel()
        carousel_indicator = Adw.CarouselIndicatorDots(carousel=self.icon_carousel)
        self.default_drop_icon = Gtk.Image(icon_name=self.DEFAULT_DROP_ICON_NAME, pixel_size=50)

        self.carousel_container.append(self.icon_carousel)
        self.carousel_container.append(carousel_indicator)

        self.icon_stack.add(self.carousel_container)
        self.icon_stack.add(self.default_drop_icon)
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

        drop_target_controller = Gtk.DropTarget(actions=Gdk.DragAction.COPY)
        drop_target_controller.set_gtypes([Gio.File, GObject.TYPE_STRING])
        drop_target_controller.connect('drop', self.on_drop_event)
        drop_target_controller.connect('enter', self.on_drop_enter)
        drop_target_controller.connect('leave', self.on_drop_leave)

        content.add_controller(drop_target_controller)

        self.drops_count = 0
        self.set_default_size(200, 200)
        self.set_resizable(False)
        self.set_content(overlay)

    def on_drop_event(self, widget, value, x, y):
        dropped_item = DroppedItem(value)
        self.drops_count += 1

        self.icon_carousel.append(dropped_item.preview_image)
        self.icon_stack.set_visible_child(self.carousel_container)
        return True

    def on_drop_enter(self, widget, x, y):
        self.default_drop_icon.set_from_icon_name('arrow2-down-symbolic')
        self.icon_stack.set_visible_child(self.default_drop_icon)
        self.drops_label.set_label(_('Release to collect'))

        return Gdk.DragAction.COPY

    def on_drop_leave(self, widget):
        if self.drops_count == 0:
            self.drops_label.set_label(self.EMPTY_DROP_TEXT)
            self.default_drop_icon.set_from_icon_name(self.DEFAULT_DROP_ICON_NAME)