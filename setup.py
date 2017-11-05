#!/usr/bin/python3

import glob, os
from distutils.core import setup

install_data = [('share/metainfo', ['data/com.github.mirkobrombin.bottles.appdata.xml']),
                ('share/applications', ['data/com.github.mirkobrombin.bottles.desktop']),
                ('share/icons/hicolor/128x128/apps',['data/com.github.mirkobrombin.bottles.svg']),
                ('share/icons/hicolor/128x128/apps',['notepad.svg']),
                ('share/icons/hicolor/128x128/apps',['wine.svg']),
                ('share/icons/hicolor/128x128/apps',['winetricks.svg']),
                ('share/icons/hicolor/128x128/apps',['wine-uninstaller.svg']),
                ('bin/bottles',['data/style.css']),
                ('bin/bottles',['bottles/constants.py']),
                ('bin/bottles',['bottles/create.py']),
                ('bin/bottles',['bottles/detail.py']),
                ('bin/bottles',['bottles/headerbar.py']),
                ('bin/bottles',['bottles/helper.py']),
                ('bin/bottles',['bottles/list.py']),
                ('bin/bottles',['bottles/main.py']),
                ('bin/bottles',['bottles/stack.py']),
                ('bin/bottles',['bottles/welcome.py']),
                ('bin/bottles',['bottles/window.py']),
                ('bin/bottles',['bottles/wine.py']),
                ('bin/bottles',['bottles/__init__.py']),
                ('bin/bottles/locale/it_IT/LC_MESSAGES',['bottles/locale/it_IT/LC_MESSAGES/bottles.mo']),
                ('bin/bottles/locale/it_IT/LC_MESSAGES',['bottles/locale/it_IT/LC_MESSAGES/bottles.po'])]

setup(  name='Bottles',
        version='0.1.2',
        author='Mirko Brombin',
        description='Easily manage your Wine bottles',
        url='https://github.com/mirkobrombin/bottles',
        license='GNU GPL3',
        scripts=['com.github.mirkobrombin.bottles'],
        packages=['bottles'],
        data_files=install_data)
