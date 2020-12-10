#!/bin/bash
BUILD_DIR="build/"
if [ -d "$BUILD_DIR" ]; then
	rm -r build
fi
mkdir build
meson build
cd build
ninja
sudo ninja install
