#!/bin/sh
BUILD_DIR="build/"
if [ -d "$BUILD_DIR" ]; then
        rm -r build
fi

# Set environment variables
# ---------------------------------------
echo "Setting environment variables"
export ARCH=x86_64
export VERSION="devel"

# Meson/ninja build
# ---------------------------------------
echo "Building with meson and ninja"
mkdir build
meson build
cd build
ninja

# Appdir
# ---------------------------------------
echo "Preparing directories"
mkdir -p appdir/usr/local/share/bottles
mkdir -p appdir/usr/bin
mkdir -p appdir/usr/share/glib-2.0/schemas/
mkdir -p appdir/usr/share/applications
mkdir -p appdir/usr/share/metainfo
mkdir -p appdir/usr/share/icons

echo "Compiling and installing glib-resources"
glib-compile-resources --sourcedir=../src/ui/ ../src/ui/bottles.gresource.xml --target=appdir/usr/local/share/bottles/bottles.gresource

echo "Copying Bottles binary"
cp src/bottles ./appdir/usr/bin/

echo "Copying Bottles python package and remove not useful files"
cp -a ../src appdir/usr/local/share/bottles/bottles
rm appdir/usr/local/share/bottles/bottles/bottles.in
rm appdir/usr/local/share/bottles/bottles/meson.build

echo "Copying appdata"
#cp -a ../data/pm.mirko.bottles.appdata.xml.in appdir/usr/share/metainfo/pm.mirko.bottles.appdata.xml

echo "Copying icons"
cp -a ../data/icons appdir/usr/share/icons

echo "Copying and compiling gschema"
cp ../data/pm.mirko.bottles.gschema.xml appdir/usr/share/glib-2.0/schemas/pm.mirko.bottles.gschema.xml
glib-compile-schemas appdir/usr/share/glib-2.0/schemas/

echo "Copying Desktop file"
cp data/pm.mirko.bottles.desktop appdir/usr/share/applications/

echo "Copying AppRun file"
cp -a ../AppRun appdir/AppRun

# Appimage
# ---------------------------------------
echo "Downloading linuxdeploy Appimage and setting executable"
wget -c -nv "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"
chmod a+x linuxdeploy-x86_64.AppImage

echo "Building Bottles Appimage"
#./linuxdeploy-x86_64.AppImage --appdir appdir --icon-file=../data/icons/hicolor/scalable/apps/pm.mirko.bottles.svg --output appimage
./linuxdeploy-x86_64.AppImage --appdir appdir  --output appimage
