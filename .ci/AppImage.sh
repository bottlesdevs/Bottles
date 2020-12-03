#!/bin/bash
#   AppImage.sh
#   Bash shell
#
#   Created by Francesco Masala
#
echo "[!] Updating Packages [!]"
sudo apt update -y 
sudo apt upgrade -y
echo "[!] Installing Packages [!]"
sudo apt install python3-pip python-dev build-essential
sudo pip3 install --upgrade pip
sudo pip3 install meson
sudo pip3 install ninja
echo "[!] Install Script [!]"
if [ "$CXX" = "g++" ]; then export CXX="g++-5" CC="gcc-5"; fi
echo "[!] Build Phase [!]"
mkdir build
meson build
cd build
ninja
# Gresource
mkdir -p appdir/usr/local/share/bottles
glib-compile-resources --sourcedir=../src/ui/ ../src/ui/bottles.gresource.xml --target=appdir/usr/local/share/bottles/bottles.gresource
# Binary
mkdir -p appdir/usr/bin ; cp src/bottles ./appdir/usr/bin/
# Package
cp -a ../src appdir/usr/local/share/bottles/bottles
rm appdir/usr/local/share/bottles/bottles/bottles.in
rm appdir/usr/local/share/bottles/bottles/meson.build
# Schemas
mkdir -p appdir/usr/share/glib-2.0/schemas/
cp ../data/pm.mirko.bottles.gschema.xml appdir/usr/share/glib-2.0/schemas/pm.mirko.bottles.gschema.xml
glib-compile-schemas appdir/usr/share/glib-2.0/schemas/ || echo "No schemas found."
# Desktop file
mkdir -p appdir/usr/share/applications ; cp data/pm.mirko.bottles.desktop appdir/usr/share/applications/
# Apprun
cp -a ../AppRun appdir/AppRun
# Linuxdeploy
wget -c -nv "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"
chmod a+x linuxdeploy-x86_64.AppImage
# Build appimage
./linuxdeploy-x86_64.AppImage --appdir appdir --icon-file=../data/icons/hicolor/scalable/apps/pm.mirko.bottles.svg --output appimage
