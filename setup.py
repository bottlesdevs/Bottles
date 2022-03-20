#!/usr/bin/python3

import glob, os
from distutils.core import setup

share_path = '/usr/share'
inst_path = share_path+'/com.usebottles.bottles/bottles'
icons_path = share_path+'/icons/hicolor/scalable/apps'

install_data = [(share_path+'/metainfo', ['data/com.usebottles.bottles.appdata.xml']),
                (share_path+'/applications', ['data/com.usebottles.bottles.desktop']),
                (icons_path,['data/com.github.mirkobrombin.bottles.svg']),
                (icons_path,['data/bottles_notepad.svg']),
                (icons_path,['data/bottles_wine.svg']),
                (icons_path,['data/bottles_winetricks.svg']),
                (icons_path,['data/bottles_wine-uninstaller.svg']),
                (icons_path,['data/bottles_wine-winecfg.svg']),
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
        version='0.2.5',
        author='Mirko Brombin',
        description='Easily manage your Wine bottles',
        url='https://github.com/mirkobrombin/bottles',
        license='GNU GPL3',
        scripts=['com.usebottles.bottles'],
        packages=['bottles'],
        data_files=install_data)
