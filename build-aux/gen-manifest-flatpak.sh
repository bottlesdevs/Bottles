#!/bin/sh
# gen-manifest.sh
#
# Render the Bottles Flatpak manifest from its template.
#
# GNOME and freedesktop SDKs use different versioning schemes:
#   - org.gnome.Sdk: release numbers (e.g. 50, 51)
#   - org.freedesktop.Sdk: year.month (e.g. 25.08, 26.08)
# These must be bumped independently. Edit the variables below,
# then run this script before invoking flatpak-builder.

set -eu

GNOME_VER="50"
FREEDESKTOP_VER="25.08"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/com.usebottles.bottles.Devel.json.template"
OUTPUT="$SCRIPT_DIR/com.usebottles.bottles.Devel.json"

sed \
  -e "s/@GNOME_VER@/$GNOME_VER/g" \
  -e "s/@FREEDESKTOP_VER@/$FREEDESKTOP_VER/g" \
  "$TEMPLATE" > "$OUTPUT"

echo "Generated: $OUTPUT (GNOME=$GNOME_VER, freedesktop=$FREEDESKTOP_VER)"
