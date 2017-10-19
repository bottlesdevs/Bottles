#!/usr/bin/python3
'''
   Copyright 2017 Mirko Brombin (brombinmirko@gmail.com)

   This file is part of Bottles.

    PPAExtender is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Bottles is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Bottles.  If not, see <http://www.gnu.org/licenses/>.
'''
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class App:
    application_id = "com.github.mirkobrombin.bottles"
    application_name = "Bottles"
    application_description = "Easily manage your Wine bottles"
    application_version ="0.0.6"
    app_years = "2017-2018"
    main_url = "https://github.com/mirkobrombin/bottles"
    bug_url = "https://github.com/mirkobrombin/bottles/issues/labels/bug"
    help_url = "https://github.com/mirkobrombin/Bottles/wiki"
    translate_url = None
    about_authors = None # Mirko Brombin <brombinmirko@gmail>
    about_documenters = None
    about_comments = application_description
    about_license_type = Gtk.License.GPL_3_0

class Colors:
    primary_color = "#2d2227"
    primary_text_color = "#f0e7e7"
    primary_text_shadow_color = "#160404"
