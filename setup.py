#!/usr/bin/python3

import glob, os
from distutils.core import setup

install_data = [('share/metainfo', ['data/com.github.mirkobrombin.ppaextender.appdata.xml']),
                ('share/applications', ['data/com.github.mirkobrombin.ppaextender.desktop']),
                ('share/icons/hicolor/128x128/apps',['data/com.github.mirkobrombin.ppaextender.svg']),
                ('bin/ppaextender',['data/style.css']),
                ('bin/ppaextender',['ppaextender/constants.py']),
                ('bin/ppaextender',['ppaextender/detail.py']),
                ('bin/ppaextender',['ppaextender/headerbar.py']),
                ('bin/ppaextender',['ppaextender/helper.py']),
                ('bin/ppaextender',['ppaextender/list.py']),
                ('bin/ppaextender',['ppaextender/main.py']),
                ('bin/ppaextender',['ppaextender/ppa.py']),
                ('bin/ppaextender',['ppaextender/stack.py']),
                ('bin/ppaextender',['ppaextender/welcome.py']),
                ('bin/ppaextender',['ppaextender/window.py']),
                ('bin/ppaextender',['ppaextender/__init__.py']),
                ('bin/ppaextender',['pkexec'])]

setup(  name='Bottles',
        version='0.0.1',
        author='Mirko Brombin',
        description='Easily manage your Wine bottles',
        url='https://github.com/mirkobrombin/bottles',
        license='GNU GPL3',
        scripts=['com.github.mirkobrombin.bottles'],
        packages=['bottles'],
        data_files=install_data)
