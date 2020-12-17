#!/usr/bin/python3
'''
    Copyright 2017 Mirko Brombin (send@mirko.pm)

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
import os
import locale
import gettext
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
except ImportError:
    import bottles.constants as cn
    import bottles.helper as hl

GLib.threads_init()

HLog = hl.HLog

# [BUG] Translations doesn't work on HLog
# [INFO] POL is PlayOnLinux
try:
    current_locale, encoding = locale.getdefaultlocale()
    locale_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
    translate = gettext.translation (cn.App.application_shortname, locale_path, [current_locale] )
    _ = translate.gettext
except FileNotFoundError:
    _ = str

class T_Winecfg(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Running Winecfg on bottle: %s' % self.working_prefix_dir))
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" winecfg", shell=True)

class T_Wintricks(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Running Winetricks on bottle: %s' % self.working_prefix_dir))
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" winetricks", shell=True)

class T_Console(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        os.chdir(self.working_prefix_dir)
        HLog.info(_('Starting a console for bottle: %s' % self.working_prefix_dir))
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wineconsole cmd", shell=True)

class T_Monitor(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Running System Monitor on bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine taskmgr", shell=True)

class T_Control(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Running Control Panel on bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine control", shell=True)

class T_Regedit(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Opening Regedit for bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine regedit", shell=True)

class T_Uninstaller(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Starting Uninstaller for bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine uninstaller", shell=True)

class T_Wineboot(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Restarting bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wineboot", shell=True)

class T_POL_Convert(threading.Thread):

    def __init__(self, working_dir, POL_working_dir, POL_name, arch, parent):
        threading.Thread.__init__(self)
        self.new_bottle_dir = working_dir+"prefix_"+POL_name
        self.POL_dir = POL_working_dir+POL_name
        self.arch = arch
        self.parent = parent
        
    def run(self):
        HLog.info(_('Converting the POL wineprefix: %s' % self.POL_dir))
        subprocess.call("cp -a "+self.POL_dir+" "+self.new_bottle_dir, shell=True)
        with open(self.new_bottle_dir+"/version.bottle", "w") as f:
            f.write(self.arch)
        self.parent.spinner.stop()

class T_Clone(threading.Thread):

    def __init__(self, working_prefix_dir, parent):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        self.parent = parent
        
    def run(self):
        HLog.info(_('Cloning the bottle: %s' % self.working_prefix_dir))
        clone_dir = self.working_prefix_dir+"_"+strftime("%Y_%m_%d__%H_%M_%S", gmtime())
        subprocess.call("cp -a "+self.working_prefix_dir+" "+clone_dir, shell=True)
        self.parent.parent.parent.hbar.spinner.stop()
        self.parent.parent.list_all.generate_entries(True)

class T_Software(threading.Thread):

    def __init__(self, working_prefix_dir, file_src):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        self.file_src = re.escape(file_src)

    def run(self):
        HLog.info(_('Running .exe in bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("WINEPREFIX="+self.working_prefix_dir+" wine "+self.file_src, shell=True)

class T_Debug(threading.Thread):

    def __init__(self, working_prefix_dir):
        threading.Thread.__init__(self)
        self.working_prefix_dir = working_prefix_dir
        
    def run(self):
        HLog.info(_('Opening a debug shell for bottle: %s' % self.working_prefix_dir))
        os.chdir(self.working_prefix_dir)
        subprocess.call("xterm -e 'WINEPREFIX="+self.working_prefix_dir+" winedbg'", shell=True)

class Wine:
    HGtk = hl.HGtk()
    working_dir = str(Path.home())+"/.Bottles/"
    working_dir_link = str(Path.home())+"/My Bottles"
    POL_working_dir = str(Path.home())+"/.PlayOnLinux/wineprefix/"

    def __init__(self, parent):
        self.parent = parent

    def get_wine_version():
        version = subprocess.check_output(["wine", "--version"])
        return str(version).replace("b'wine-", "").replace("\\n'", "")

    def check_work_dir(self):
        HLog.info(_('Checking for .Bottles directory on: %s' % self.working_dir))
        if not os.path.exists(self.working_dir):
            HLog.warning('[NO_BOTTLES_DIR] '+_('I did not find the Bottles directory, creating in: %s' % self.working_dir))
            os.mkdir(self.working_dir)
            HLog.info(_('Directory created, now creating the symlink: %s' % self.working_dir_link))
            os.symlink(self.working_dir, self.working_dir_link)
        else:
            HLog.success(_('Bottles directory founded!'))    

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
        self.parent.parent.parent.hbar.spinner.set_tooltip_text(_('Cloning the bottle..'))
        self.parent.parent.parent.hbar.spinner.start()
        T_Clone(working_dir, self.parent).start()
    
    def run_software(self, working_dir, file_src):
        T_Software(working_dir, file_src).start()

    def check_special_chars(self, string):
        if not re.match(r'^\w+$', string):
            HLog.error('[BOTTLE_NAME_ERROR] '+_('Bottle name can not contain special characters'))
            # Notice for posterity: "parent.parent.parent ...." NEVER do this please. I am a goat.
            message_dialog = Gtk.MessageDialog(parent=self.parent.parent,
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                message_format=_('Bottle name can not contain special characters')
            )
            message_dialog.connect("response", self.md_ok)
            message_dialog.show_all()
            return False
        else:
            return True

    def create_bottle(self, name, arch):
        if self.check_special_chars(name):
            # create dir
            self.working_prefix_dir = self.working_dir+"prefix_"+name
            if not os.path.exists(self.working_prefix_dir):
                # create new bottle
                HLog.info(_('Creating new bottle with arch: %s' % arch))
                if arch == "32 Bit":
                    w_arch = "win32"
                else:
                    w_arch = "win64"
                subprocess.call("WINEPREFIX="+self.working_prefix_dir+" WINEARCH="+w_arch+" wine wineboot", shell=True)
                # create version file
                version_bottle = self.working_prefix_dir+"/version.bottle"
                with open(version_bottle, "w") as f:
                    f.write(arch)
            else:
                HLog.warning('[BOTTLE_ALREADY_EXISTS] '+_('There is already a bottle named: %s, redirecting to it.' % name))
            self.detail_bottle(name)
            
            # re-fill list
            lt = self.parent.parent.stack.list_all
            lt.generate_entries(True)

    def list_bottles(self):
        HLog.info(_('Generating the bottles list..'))
        bottles = []
        try:
            walk = next(os.walk(self.working_dir))[1]
            for w in walk:
                # Arch
                try:
                    with open(self.working_dir+w+"/version.bottle",'r') as arch_f:
                        arch=arch_f.read().replace('\n', '')
                except FileNotFoundError:
                    HLog.warning('[NO_VERSION_FILE] '+_('I can not find the version file for %s, I assume it is a 32 Bit.' % w))
                    arch = "32 Bit"
                # Size
                size = subprocess.run(['du', '-sh', self.working_dir+w], stdout=subprocess.PIPE)
                size = str(size.stdout).split('\\t', 1)[0].replace("b'", '')
                bottles.append([w, arch, size])
        except StopIteration:
            pass
        return bottles

    def list_POLs(self):
        HLog.info(_('Generating the POL wineprefix list..'))
        POLs = []
        try:
            walk = next(os.walk(self.POL_working_dir))[1]
            for w in walk:
                try:
                    with open(self.POL_working_dir+w+"/playonlinux.cfg",'r') as f:
                        rows = f.readlines()
                        # Arch
                        if rows[0].startswith("ARCH="):
                            arch = rows[0]
                        elif rows[1].startswith("ARCH="):
                            arch = rows[1]
                        else:
                            arch = rows[2]
                        arch = arch.replace('\n', '').replace('ARCH=', '')
                        arch = '32 Bit' if arch == 'x86' else '64 Bit'
                        # Version
                        if rows[0].startswith("VERSION="):
                            version = rows[0]
                        elif rows[1].startswith("VERSION="):
                            version = rows[1]
                        else:
                            version = rows[2]
                        version = version.replace('\n', '').replace('VERSION=', '')
                        # Size
                        size = subprocess.run(['du', '-sh', self.POL_working_dir+w], stdout=subprocess.PIPE)
                        size = str(size.stdout).split('\\t', 1)[0].replace("b'", '')
                    POLs.append([w, arch, version, size])
                except FileNotFoundError:
                    HLog.warning('[POL_WITHOUT_CONFIG] '+_('The POL wineprefix: %s does not contain the configuration file. Ignoring' % w))
                    pass
        except StopIteration:
            pass
        return POLs
        
    def remove_bottle(self, bottle_name):
        HLog.info(_('Removing bottle: %s' % bottle_name))
        if self.check_special_chars(bottle_name):
            shutil.rmtree(self.working_dir+bottle_name, ignore_errors=True)

            # re-fill list
            lt = self.parent.parent.stack.list_all
            lt.generate_entries(True)

    def convert_POL(self, POL_name, arch):
        message_dialog = Granite.MessageDialog.new_with_image_from_icon_name(
            "POL_TO_BOTTLE_DISCLAIMER",
            _('This process converts the POL wineprefix into a bottle. \n\nNote that Bottles uses the Wine version installed on the system. After the conversion, the programs installed in the bottle may not work properly.\n\nThe original version of the POL wineprefix will remain intact.'),
            "dialog-warning",
            Gtk.ButtonsType.CANCEL
        )
        message_dialog.set_transient_for(self.parent.parent)
        message_dialog.set_flags = Gtk.DialogFlags.MODAL
        message_dialog.connect("response", self.md_ok)
        message_dialog.show_all()
        self.parent.spinner.set_tooltip_text(_('Converting POL to bottle..'))
        self.parent.spinner.start()
        T_POL_Convert(self.working_dir, self.POL_working_dir, POL_name, arch, self.parent).start()

    def detail_bottle(self, name):
        HLog.info(_('Loading details for bottle: %s' % name))
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
        HLog.info(_('This is a %s bottle' % arch))
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
        self.parent.props.title = name+" "+version+" ("+arch+")"

        # change stack to detail
        self.parent.save.hide()
        self.parent.parent.stack.stack.set_visible_child_name("detail")
        
    '''
    MessageDialog responses
    '''
    def md_ok(self, widget, response_id):
        widget.destroy()
