#!/bin/bash
BUILD_DIR="build/"
if [ -d "$BUILD_DIR" ]; then
	echo "Build directory not found, check if Bottles is installed."
fi
sudo ninja uninstall -C $BUILD_DIR
