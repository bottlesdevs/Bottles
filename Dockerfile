FROM ubuntu:jammy

RUN apt update 
RUN apt install -y debhelper python3 python3-pip python3-setuptools python3-yaml python3-requests gettext build-essential patchelf librsvg2-dev desktop-file-utils libgdk-pixbuf2.0-dev fakeroot strace ninja-build meson winbind wget

RUN wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O /opt/appimagetool-x86_64.AppImage
RUN cd /opt && chmod +x appimagetool-x86_64.AppImage && ./appimagetool-x86_64.AppImage --appimage-extract 
RUN cd /opt && mv squashfs-root appimagetool-x86_64.AppDir && ls && ln -s /opt/appimagetool-x86_64.AppDir/AppRun /usr/bin/appimagetool 

RUN DEBIAN_FRONTEND=noninteractive apt install -y  git libhandy-1-dev appstream-util

RUN pip3 install git+https://github.com/AppImageCrafters/appimage-builder.git
