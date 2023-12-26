#!/usr/bin/python3

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
gi.require_version('Adw', '1')

from gi.repository import Wnck



wnck_screen = Wnck.Screen.get_default()

print(wnck_screen.get_workspaces())
wnck_windows = wnck_screen.get_windows()

print(wnck_windows)
for w in wnck_windows:
    print(w.get_name())
    print(w.get_pid())
    print(w.get_application())