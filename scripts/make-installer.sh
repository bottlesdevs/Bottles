#!/bin/sh

# The is a script for making an offline installer for Bottles.
# Install the Bottles flatpak. Then open the program once with an internet connection.
# The close the program when the setup is complete.
# Then open this script as a program.
# If other flatpaks were installed, they will be copied as well.
# As an example, MangoHud will be included as well if a person installed it.

mkdir ./installer/

mkdir ./installer/Bottles/

mkdir ./installer/Bottles/data/

mkdir ./installer/Bottles/data/var/

mkdir ./installer/Bottles/data/var/lib/

echo "Copying folders and files..."

sudo chmod -R 755 /var/lib/flatpak

cp -R /var/lib/flatpak ./installer/Bottles/data/var/lib/

part1="/home/"

part2=$(whoami)

part3="/.var"

directory=$part1$part2$part3

cp -R $directory ./installer/Bottles/data/

echo "Copying the install file..."

cp  ./install.sh ./installer/Bottles/

echo "The installer has been created. Making the archive..."

tar -czvf Bottles.tar.gz ./installer/

echo "The archive has been made."

sleep 2
