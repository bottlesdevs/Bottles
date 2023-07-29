#!/usr/bin/env bash
BUILD_DIR="build/"
if [ -d "$BUILD_DIR" ]; then
	rm -r build
fi
mkdir build
meson --prefix=$PWD/build build
ninja -j$(nproc) -C build install