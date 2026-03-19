#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MANIFEST="$SCRIPT_DIR/com.usebottles.bottles.Devel.json"
BUILD_DIR="$PROJECT_DIR/build-dir"
APP_ID="com.usebottles.bottles.Devel"

echo "==> Building $APP_ID"
echo "    Manifest: $MANIFEST"
echo "    Build dir: $BUILD_DIR"

host-spawn flatpak run org.flatpak.Builder \
    --force-clean \
    --disable-rofiles-fuse \
    --user \
    --install \
    --state-dir "$PROJECT_DIR/.flatpak-builder" \
    "$BUILD_DIR" \
    "$MANIFEST"

echo "==> Build complete. Run with:"
echo "    host-spawn flatpak run $APP_ID"
