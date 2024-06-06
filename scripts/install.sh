#!/bin/sh

echo "Copying folders and files..."

sudo cp -R -n ./data/var/lib/flatpak* /var/lib/

part1="/home/"

part2=$(whoami)

part3="/"

directory=$part1$part2$part3

cp -R -n ./data/.var $directory

echo "Installation is complete."

sleep 2
