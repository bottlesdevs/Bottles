#!/bin/sh

# Set environment variables
ARCH=x86_64

# Meson/ninja build
mkdir build
meson build
cd build
ninja

# Appimage
# - gresource
mkdir -p appdir/usr/local/share/bottles
glib-compile-resources --sourcedir=../src/ui/ ../src/ui/bottles.gresource.xml --target=appdir/usr/local/share/bottles/bottles.gresource
# - binary
mkdir -p appdir/usr/bin ; cp src/bottles ./appdir/usr/bin/
# - package
cp -a ../src appdir/usr/local/share/bottles/bottles
rm appdir/usr/local/share/bottles/bottles/bottles.in
rm appdir/usr/local/share/bottles/bottles/meson.build
# - schemas
mkdir -p appdir/usr/share/glib-2.0/schemas/
cp ../data/pm.mirko.bottles.gschema.xml appdir/usr/share/glib-2.0/schemas/pm.mirko.bottles.gschema.xml
- glib-compile-schemas appdir/usr/share/glib-2.0/schemas/ || echo "No schemas found."
# - desktop file
mkdir -p appdir/usr/share/applications ; cp data/pm.mirko.bottles.desktop appdir/usr/share/applications/
# - apprun
cp -a ../AppRun appdir/AppRun
# - linuxdeploy
wget -c -nv "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"
chmod a+x linuxdeploy-x86_64.AppImage
# - build appimage
./linuxdeploy-x86_64.AppImage --appdir appdir --icon-file=../data/icons/hicolor/scalable/apps/pm.mirko.bottles.svg --output appimage
