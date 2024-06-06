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

echo "Making the desktop file..."

printf '[Desktop Entry]
Name=Bottles
Categories=Utility;
Exec=/usr/bin/flatpak run --branch=stable --arch=x86_64 --command=bottles --file-forwarding com.usebottles.bottles @@u %u @@
Comment=Open Windows programs and games with environments.
Terminal=false
PrefersNonDefaultGPU=false
Icon=/var/lib/flatpak/appstream/flathub/x86_64/f72e385b85e02c8672444f970b7660372b9258958f54f952a03f8d849d032586/icons/128x128/com.usebottles.bottles.png
Type=Application' > ./installer/Bottles/Bottles.desktop

echo "Copying the install file..."

cp  ./install.sh ./installer/Bottles/

echo "The installer has been created. Making the archive..."

7z a -r Bottles ./installer/Bottles/

echo "The archive has been made."

sleep 2
