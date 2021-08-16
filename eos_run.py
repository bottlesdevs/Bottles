#!/usr/bin/python3
import os
import sys
import signal
import gettext

VERSION = "2021.8.14"
pkgdatadir = "/app/usr/local/share/bottles"
localedir = "/app/usr/share/local/locale"
gresource_path = f"{pkgdatadir}/bottles.gresource"
sys.path.insert(1, pkgdatadir)

signal.signal(signal.SIGINT, signal.SIG_DFL)
gettext.install('bottles', localedir)

if __name__ == '__main__':
    import gi

    from gi.repository import Gio
    resource = Gio.Resource.load(gresource_path)
    resource._register()

    from bottles import main
    sys.exit(main.main(VERSION))