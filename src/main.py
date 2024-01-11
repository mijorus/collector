# main.py
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

import sys
import gi
import os
import shutil
import logging
import os

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Adw', '1')

from .lib.constants import *
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
from .window import CollectorWindow

LOG_FILE_MAX_N_LINES = 5000
LOG_FOLDER = GLib.get_user_cache_dir() + '/logs'

class CollectorApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self, version):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        
        self.version = version
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action)
        self.create_action('shortcuts', self.on_shortcuts_action)
        self.create_action('open_log_file', self.on_open_log_file)
        self.create_action('open_welcome_screen', self.on_open_welcome_screen)

    def do_startup(self):
        logging.warn('\n\n--- App startup ---')
        Adw.Application.do_startup(self)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/it/mijorus/collector/assets/style.css')
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        """Called when the application is activated.

        We raise the application's main window, creating it if
        necessary.
        """
        w_index = len(self.get_windows())

        win = CollectorWindow(window_index=w_index, application=self)

        if not self.get_windows():
            if os.path.exists(win.DROPS_BASE_PATH):
                logging.debug('Removing ' +  win.DROPS_BASE_PATH)
                shutil.rmtree(win.DROPS_BASE_PATH)

        self.add_window(win)

        win.present()

    def on_about_action(self, widget, _):
        """Callback for the app.about action."""
        about = Adw.AboutWindow(transient_for=self.props.active_window,
                                application_name='Collector',
                                application_icon=APP_ID,
                                developer_name='Lorenzo Paderi',
                                version=self.version,
                                developers=['Lorenzo Paderi'],
                                copyright='© 2023 Lorenzo Paderi')
        about.present()

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        print('app.preferences action activated')

    def on_open_log_file(self, widget, data):
        log_gfile = Gio.File.new_for_path(f'{GLib.get_user_cache_dir()}/logs')
        launcher = Gtk.FileLauncher.new(log_gfile)
        launcher.launch()

    def on_open_welcome_screen(self, widget, data):
        pass

    def on_shortcuts_action(self, widget, data):
        bl = Gtk.Builder.new_from_resource('/it/mijorus/collector/gtk/shortcuts.ui')
        shortcuts_window = bl.get_object('shortcuts-builder')
        shortcuts_window.set_transient_for(self.props.active_window)
        shortcuts_window.present()

    def create_action(self, name, callback, shortcuts=None):
        """Add an application action.

        Args:
            name: the name of the action
            callback: the function to be called when the action is
              activated
            shortcuts: an optional list of accelerators
        """
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)
        if shortcuts:
            self.set_accels_for_action(f"app.{name}", shortcuts)


def main(version):
    """The application's entry point."""
    print( os.environ.get('APP_DEBUG', False))
    if os.environ.get('APP_DEBUG', False) == '1':
        logging.basicConfig(
            stream=sys.stdout,
            encoding='utf-8',
            level= logging.DEBUG,
            force=True
        )
    else:
        if not os.path.exists(LOG_FOLDER):
            os.makedirs(LOG_FOLDER)

        log_file = f'{LOG_FOLDER}/collector.log'
        if os.path.exists(log_file) and \
            os.stat(log_file).st_size > LOG_FILE_MAX_N_LINES:
            with open(log_file, 'w+') as f:
                f.write('')

        print(f'Logging to file {log_file}')
        logging.basicConfig(
            filename=log_file,
            filemode='a',
            encoding='utf-8',
            level= logging.WARN,
            force=True
        )

    app = CollectorApplication(version)
    return app.run(sys.argv)
