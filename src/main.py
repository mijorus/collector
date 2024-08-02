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
import argparse
import logging
import os

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Adw', '1')

from .lib.constants import *
from gi.repository import Gtk, Gio, Adw, Gdk, GLib
from .window import CollectorWindow
from .preferences import SettingsWindow
from .lib.utils import get_gsettings, on_click_open_uri

LOG_FILE_MAX_N_LINES = 5000
LOG_FOLDER = GLib.get_user_cache_dir() + '/logs'
MAX_WINDOWS_FROM_ARGS = 5

class CollectorApplication(Adw.Application):
    """The main application singleton class."""

    def __init__(self, version):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        
        self.version = version
        self.create_action('quit', lambda *_: self.quit(), ['<primary>q'])
        self.create_action('about', self.on_about_action)
        self.create_action('preferences', self.on_preferences_action, ['<primary>comma'])
        self.create_action('open_log_file', self.on_open_log_file)
        self.create_action('open_welcome_screen', self.on_open_welcome_screen)

        self.add_main_option_entries([
            self.make_option('w')
        ])

        self.n_of_windows = 1

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

        parser = argparse.ArgumentParser()
        parser.add_argument('--w', type=int)

        n_of_windows = 1
        args = parser.parse_args()
        if args.w:
            n_of_windows = args.w if args.w < MAX_WINDOWS_FROM_ARGS else 1

        w_index = len(self.get_windows())

        if not self.get_windows():
            if os.path.exists(CollectorWindow.DROPS_BASE_PATH):
                logging.debug('Removing ' +  CollectorWindow.DROPS_BASE_PATH)
                shutil.rmtree(CollectorWindow.DROPS_BASE_PATH)
        else:
            n_of_windows = 1

        logging.debug(f'Opening {n_of_windows} windows')
        for n in range(n_of_windows):
            win = CollectorWindow(window_index=(w_index + n), application=self)
            self.add_window(win)

            win.present()

    def on_about_action(self, *args):
        """Callback for the app.about action."""
        about = Adw.AboutWindow(transient_for=self.props.active_window,
                                application_name='Collector',
                                application_icon=APP_ID,
                                developer_name='Lorenzo Paderi',
                                version=self.version,
                                developers=['Lorenzo Paderi'],
                                # Translators: Replace "translator-credits" with your names, one name per line
                                translator_credits=_("translator-credits"),
                                copyright='© 2023 Lorenzo Paderi')
    
        about.add_credit_section('Icon by', ['Jakub Steiner'])
        about.present()

    def on_preferences_action(self, widget, _):
        """Callback for the app.preferences action."""
        pref = SettingsWindow()
        pref.set_transient_for(self.props.active_window)
        pref.present()

    def on_open_log_file(self, widget, data):
        log_gfile = Gio.File.new_for_path(f'{GLib.get_user_cache_dir()}/logs')
        launcher = Gtk.FileLauncher.new(log_gfile)
        launcher.launch()

    def on_open_welcome_screen(self, widget, data):
        on_click_open_uri(None, 'https://mijorus.it/projects/collector/tutorial')

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

    # thank you mate ❤️
    # https://github.com/gtimelog/gtimelog/blob/6e4b07b58c730777dbdb00b3b85291139f8b10aa/src/gtimelog/main.py#L159
    def make_option(self, long_name, short_name=None, flags=0, arg=0, arg_data=None, description=None, arg_description=None):
        # surely something like this should exist inside PyGObject itself?!
        option = GLib.OptionEntry()
        option.long_name = long_name.lstrip('-')
        option.short_name = 0 if not short_name else short_name.lstrip('-')
        option.flags = flags
        option.arg = arg
        option.arg_data = arg_data
        option.description = description
        option.arg_description = arg_description
        return option

def main(version):
    """The application's entry point."""
    if os.environ.get('APP_DEBUG', False) == '1':
        logging.basicConfig(
            stream=sys.stdout,
            encoding='utf-8',
            level= logging.DEBUG,
            force=True
        )
    else:
        debug_logs = get_gsettings().get_boolean('debug-logs')
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
            level= logging.DEBUG if debug_logs else logging.WARN,
            force=True
        )

    app = CollectorApplication(version)
    return app.run(sys.argv)
