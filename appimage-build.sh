#!/bin/bash
BUILD_DIR="build/"
if [ -d "$BUILD_DIR" ]; then
        sudo rm -r build
fi

red="\e[0;91m"
blue="\e[0;94m"
expand_bg="\e[K"
blue_bg="\e[0;104m${expand_bg}"
red_bg="\e[0;101m${expand_bg}"
green_bg="\e[0;102m${expand_bg}"
green="\e[0;92m"
black="\e[30m"
white="\e[0;97m"
bold="\e[1m"
uline="\e[4m"
reset="\e[0m"

function title {
	PREFIX="\n$bold-----"
	SUFFIX="--$reset"
	echo -e "$PREFIX $1 $SUFFIX"
}

function print_execution {
	if $1; then
		echo -e "$green_bg$bold$black-- $1$reset"
	else
		echo -e "$red_bg$bold$black-- Operation failed for: $1$reset"
	fi
}

# Set linuxdeploy env
# ---------------------------------------
export LINUXDEPLOY=./linuxdeploy-x86_64.AppImage

# Set environment variables
# ---------------------------------------
if [[ -v NO_ENVIRONMENT ]]; then
	title "No environment variables need to be defined"
else
	title "Setting environment variables"
	export ARCH=x86_64
	export VERSION="devel"
fi

# Meson/ninja build
# ---------------------------------------
title "Building with meson and ninja"
print_execution "mkdir build"
print_execution "meson build"
print_execution "cd build"
print_execution "ninja"
print_execution "ninja bottles-pot"
print_execution "ninja bottles-update-po"

# Appdir
# ---------------------------------------
title "Preparing directories"
print_execution "mkdir -p appdir/usr/local/share/bottles"
print_execution "mkdir -p appdir/usr/bin"
print_execution "mkdir -p appdir/usr/share/glib-2.0/schemas"
print_execution "mkdir -p appdir/usr/share/applications"
print_execution "mkdir -p appdir/usr/share/metainfo"
print_execution "mkdir -p appdir/usr/share/icons"

title "Compiling and installing glib-resources"
print_execution "glib-compile-resources --sourcedir=../src/ui/ ../src/ui/bottles.gresource.xml --target=appdir/usr/local/share/bottles/bottles.gresource"


title "Copying Bottles binary"
print_execution "cp src/bottles ./appdir/usr/bin/"

title "Copying Bottles python package and remove not useful files"
print_execution "cp -a ../src appdir/usr/local/share/bottles/bottles"
print_execution "rm appdir/usr/local/share/bottles/bottles/bottles.in"
print_execution "rm appdir/usr/local/share/bottles/bottles/meson.build"

if [[ -v NO_ENVIRONMENT ]]; then
	title "Copying appdata"
	print_execution "cp -a ../data/com.usebottles.bottles.appdata.xml.in appdir/usr/share/metainfo/com.usebottles.bottles.appdata.xml"
fi

title "Compiling and installing translations"
cat ../po/LINGUAS | while read lang
do
	print_execution "mkdir -p appdir/usr/share/locale/$lang/LC_MESSAGES"
	print_execution "msgfmt -o appdir/usr/share/locale/$lang/LC_MESSAGES/bottles.mo ../po/$lang.po"
done

title "Copying icons"
print_execution "cp -a ../data/icons appdir/usr/share"
print_execution "mv appdir/usr/share/icons/symbolic/scalable/apps/*.svg appdir/usr/share/icons/hicolor/scalable/apps/"

title "Copying and compiling gschema"
print_execution "cp ../data/com.usebottles.bottles.gschema.xml appdir/usr/share/glib-2.0/schemas/com.usebottles.bottles.gschema.xml"
print_execution "glib-compile-schemas appdir/usr/share/glib-2.0/schemas/"

title "Copying Desktop file"
print_execution "cp data/com.usebottles.bottles.desktop appdir/usr/share/applications/"

title "Copying AppRun file"
print_execution "cp -a ../AppRun appdir/AppRun"

# Appimage
# ---------------------------------------
title "Downloading linuxdeploy Appimage and setting executable"
print_execution "curl -L https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage --output linuxdeploy-x86_64.AppImage"
print_execution "chmod a+x linuxdeploy-x86_64.AppImage"

title "Downloading linuxdeploy-plugin-gtk"
print_execution "curl -L https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh --output linuxdeploy-plugin-gtk.sh"
print_execution "sed -i 's/ldd/true/g' ./linuxdeploy-plugin-gtk.sh" #uses static, not dynamic libraries
cat ./linuxdeploy-plugin-gtk.sh
print_execution "chmod a+x linuxdeploy-plugin-gtk.sh"

title "Executing linuxdeploy-plugin-gtk on appdir"
export DEPLOY_GTK_VERSION=4
print_execution "./linuxdeploy-plugin-gtk.sh --appdir appdir"

title "Building Bottles Appimage"
print_execution "./linuxdeploy-x86_64.AppImage --appdir appdir  --output appimage"
