#!/usr/bin/python3
'''
   Copyright 2017 Mirko Brombin (brombinmirko@gmail.com)

   This file is part of Bottles.

    Bottles is free software: you can redistribute it and/or modify
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

import os
import gi
import re
import threading
import subprocess
import shutil
import random
import time
from time import gmtime, strftime
from pathlib import Path
import webbrowser
gi.require_version('Gtk', '3.0')
gi.require_version('Granite', '1.0')
from gi.repository import Gtk, Gdk, Granite, GObject, GLib, GdkPixbuf
try:
    import constants as cn
    import helper as hl
    import alert as al
except ImportError:
    import bottles.constants as cn
    import bottles.helper as hl
    import bottles.alert as al

GLib.threads_init()

class T_Winecfg(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" winecfg", shell=True)

class T_Wintricks(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" winetricks", shell=True)

class T_Console(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wineconsole cmd", shell=True)

class T_Monitor(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine taskmgr", shell=True)

class T_Control(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine control", shell=True)

class T_Regedit(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine regedit", shell=True)

class T_Uninstaller(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine uninstaller", shell=True)

class T_Wineboot(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wineboot", shell=True)

class T_Clone(threading.Thread):

    def __init__(self, working_prefix_dir, parent):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        self.parent = parent
        
    def run(self):
        clone_dir = self.working_prefix_dir+"_"+strftime("%Y_%m_%d__%H_%M_%S", gmtime())
        subprocess.call("cp -a "+self.working_prefix_dir+" "+clone_dir, shell=True)
        self.parent.parent.parent.hbar.spinner.stop()
        self.parent.parent.list_all.generate_entries(True)

class T_Software(threading.Thread):

    def __init__(self, working_prefix_dir, file_src):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        self.file_src = file_src
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine "+self.file_src, shell=True)

class T_Debug(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        subprocess.call("xterm -e 'WINEPREFIX="+self.working_prefix_dir+" winedbg'", shell=True)

class Wine:
    HGtk = hl.HGtk()
    working_dir = str(Path.home())+"/.Bottles/"
    working_dir_link = str(Path.home())+"/My Bottles"
    wine_icon = Gtk.IconTheme.get_default().load_icon("wine", 16, 0)

    def __init__(self, parent):
        self.parent = parent

    def check_work_dir(self):
        if not os.path.exists(self.working_dir):
            os.mkdir(self.working_dir)
            os.symlink(self.working_dir, self.working_dir_link)
			
    
    def run_winecfg(self, working_dir):
        T_Winecfg(working_dir).start()
    
    def run_winetricks(self, working_dir):
        T_Wintricks(working_dir).start()
    
    def run_console(self, working_dir):
        T_Console(working_dir).start()
    
    def run_monitor(self, working_dir):
        T_Monitor(working_dir).start()
    
    def run_control(self, working_dir):
        T_Control(working_dir).start()
    
    def run_regedit(self, working_dir):
        T_Regedit(working_dir).start()
    
    def run_uninstaller(self, working_dir):
        T_Uninstaller(working_dir).start()
    
    def run_wineboot(self, working_dir):
        T_Wineboot(working_dir).start()
    
    def run_debug(self, working_dir):
        T_Debug(working_dir).start()
    
    def run_clone(self, working_dir):
        self.parent.parent.parent.hbar.spinner.start()
        T_Clone(working_dir, self.parent).start()
    
    def run_software(self, working_dir, file_src):
        T_Software(working_dir, file_src).start()

    def check_special_chars(self, string):
        if not re.match(r'^\w+$', string):
            alert = al.Alert(self.parent.parent,
                "BOTTLE_NAME_ERROR: Bottle name can not contain special characters",
                600, 90
            )
            response = alert.run()
            if response == Gtk.ResponseType.OK:
                alert.destroy()
            return False
        else:
            return True

    def create_bottle(self, name, arch):
        if self.check_special_chars(name):
            print("Creating a bottle with name: "+name+" and arch: "+arch)

            # create dir
            self.working_prefix_dir = self.working_dir+"prefix_"+name
            if not os.path.exists(self.working_prefix_dir):
                os.mkdir(self.working_prefix_dir)
                version_bottle = self.working_prefix_dir+"/version.bottle"
                with open(version_bottle, "w") as f:
                    f.write(arch)

                # start winecfg
                self.run_winecfg(self.working_prefix_dir)

            self.detail_bottle(name)
            
            # re-fill list
            lt = self.parent.parent.stack.list_all
            lt.generate_entries(True)

    def list_bottles(self):
        bottles = []
        try:
            walk = next(os.walk(self.working_dir))[1]
            for w in walk:
                bottles.append(w)
        except StopIteration:
            pass
        return bottles

    def remove_bottle(self, bottle_name):
        if self.check_special_chars(bottle_name):
            shutil.rmtree(self.working_dir+bottle_name, ignore_errors=True)

            # re-fill list
            lt = self.parent.parent.stack.list_all
            lt.generate_entries(True)

    def detail_bottle(self, name):
        # get detail data
        dt = self.parent.parent.stack.detail
        self.parent.properties.hide()
        self.parent.trash.hide()
        if name.find("prefix_") == -1:
            dt.working_dir = self.working_dir+"prefix_"+name
        else:
            dt.working_dir = self.working_dir+name
        with open(dt.working_dir+"/version.bottle",'r') as arch_f:
            arch=arch_f.read().replace('\n', '')
        if arch == "32 Bit":
            version = subprocess.check_output(["wine", "--version"])
        else:
            version = subprocess.check_output(["wine64", "--version"])
        version = str(version)
        version = version.replace("b'", "")
        version = version.replace("\\n'", "")

        # remove prefix_ from bottle name
        name = name.replace("prefix_", "")

        # set detail title and description
        dt.title.set_text(name)
        dt.description.set_text(version+" ("+arch+")")

        # change stack to detail
        self.parent.save.hide()
        self.parent.parent.stack.stack.set_visible_child_name("detail")
        

