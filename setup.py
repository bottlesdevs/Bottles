#!/usr/bin/python3

import glob, os
from distutils.core import setup

inst_path = '/usr/share/com.github.mirkobrombin.bottles/bottles'

install_data = [('/usr/share/metainfo', ['data/com.github.mirkobrombin.bottles.appdata.xml']),
                ('/usr/share/applications', ['data/com.github.mirkobrombin.bottles.desktop']),
                ('/usr/share/icons/hicolor/scalable/apps',['data/com.github.mirkobrombin.bottles.svg']),
                ('/usr/share/icons/hicolor/scalable/apps',['data/notepad.svg']),
                ('/usr/share/icons/hicolor/scalable/apps',['data/wine.svg']),
                ('/usr/share/icons/hicolor/scalable/apps',['data/winetricks.svg']),
                ('/usr/share/icons/hicolor/scalable/apps',['data/wine-uninstaller.svg']),
                ('/usr/share/icons/hicolor/scalable/apps',['data/wine-winecfg.svg']),
                (inst_path,['data/style.css']),
                (inst_path,['bottles/constants.py']),
                (inst_path,['bottles/create.py']),
                (inst_path,['bottles/detail.py']),
                (inst_path,['bottles/headerbar.py']),
                (inst_path,['bottles/helper.py']),
                (inst_path,['bottles/importer.py']),
                (inst_path,['bottles/list.py']),
                (inst_path,['bottles/main.py']),
                (inst_path,['bottles/stack.py']),
                (inst_path,['bottles/welcome.py']),
                (inst_path,['bottles/window.py']),
                (inst_path,['bottles/wine.py']),
                (inst_path,['bottles/__init__.py']),
                (inst_path+'/locale/it_IT/LC_MESSAGES',['bottles/locale/it_IT/LC_MESSAGES/bottles.mo']),
                (inst_path+'/locale/it_IT/LC_MESSAGES',['bottles/locale/it_IT/LC_MESSAGES/bottles.po']),
                (inst_path+'/locale/es_ES/LC_MESSAGES',['bottles/locale/es_ES/LC_MESSAGES/bottles.mo']),
                (inst_path+'/locale/es_ES/LC_MESSAGES',['bottles/locale/es_ES/LC_MESSAGES/bottles.po']),
                (inst_path+'/locale/fr_FR/LC_MESSAGES',['bottles/locale/fr_FR/LC_MESSAGES/bottles.mo']),
                (inst_path+'/locale/fr_FR/LC_MESSAGES',['bottles/locale/fr_FR/LC_MESSAGES/bottles.po']),
                (inst_path+'/locale/de_DE/LC_MESSAGES',['bottles/locale/de_DE/LC_MESSAGES/bottles.mo']),
                (inst_path+'/locale/de_DE/LC_MESSAGES',['bottles/locale/de_DE/LC_MESSAGES/bottles.po']),]

setup(  name='Bottles',
        version='0.1.6',
        author='Mirko Brombin',
        description='Easily manage your Wine bottles',
        url='https://github.com/mirkobrombin/bottles',
        license='GNU GPL3',
        scripts=['com.github.mirkobrombin.bottles'],
        packages=['bottles'],
        data_files=install_data)
