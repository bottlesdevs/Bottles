#!/bin/sh

run_flatpak() {
    flatpak-spawn --host flatpak run org.flatpak.Builder build com.usebottles.bottles.yml --user --install --force-clean && flatpak-spawn --host flatpak run com.usebottles.bottles
}

run_host() {
    flatpak run org.flatpak.Builder build com.usebottles.bottles.yml --user --install --force-clean && flatpak run com.usebottles.bottles
}

run_container() {
    host-spawn flatpak run org.flatpak.Builder build com.usebottles.bottles.yml --user --install --force-clean && host-spawn flatpak run com.usebottles.bottles
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
