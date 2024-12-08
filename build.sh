#!/bin/sh

run_flatpak() {
  flatpak-spawn --host flatpak-builder -v build build-aux/com.usebottles.bottles.Devel.json --user --install --force-clean && flatpak-spawn --host flatpak run com.usebottles.bottles.Devel
}

run_host() {
  flatpak-builder build -v build-aux/com.usebottles.bottles.Devel.json --user --install --force-clean && flatpak run com.usebottles.bottles.Devel
}

run_container() {
  host-spawn flatpak-builder build -v build-aux/com.usebottles.bottles.Devel.json --user --install --force-clean && host-spawn flatpak run com.usebottles.bottles.Devel
}

if [ -x "$(command -v flatpak-spawn)" ]; then
  run_flatpak
  exit $?
fi

if [ -f "/run/.containerenv" ]; then
  if [ -x "$(command -v flatpak)" ]; then
    run_host
    exit $?
  fi

  if [ -x "$(command -v host-spawn)" ]; then
    run_container
    exit $?
  fi

  echo "Looks like you are running in a container, but you don't have flatpak or host-spawn installed."
  echo "Nothing to do here."
fi

run_host
exit $?
