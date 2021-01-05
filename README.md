<div align="center">
  <img src="https://raw.githubusercontent.com/bottlesdevs/Bottles/c015a96257000498fff183c59c482100806fd320/data/icons/hicolor/scalable/apps/com.usebottles.bottles.svg" width="64">
  <h1 align="center">Bottles v2</h1>
  <p align="center">Easily manage wineprefix using environments</p>
  <small>⚠️ This version is under development. <a href="https://github.com/bottlesdevs/Bottles/tree/v1">Here</a> you can find the stable v1.</small>
</div>

<br/>

<div align="center">
   <a href="https://hosted.weblate.org/engage/bottles/">
      <img src="https://hosted.weblate.org/widgets/bottles/-/bottles/svg-badge.svg" alt="Stato traduzione" />
   </a>
   <a href="https://www.codacy.com/gh/bottlesdevs/Bottles/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=bottlesdevs/Bottles&amp;utm_campaign=Badge_Grade">
        <img src="https://app.codacy.com/project/badge/Grade/1f8c35825c7c45a58a48a21b79764387"/>
   </a>
   <a href="https://git.mirko.pm/brombinmirko/Bottles/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg">
   </a>
   <a href="https://travis-ci.com/github/bottlesdevs/Bottles">
    <img src="https://travis-ci.com/bottlesdevs/Bottles.svg?branch=develop">
   </a>
  <a href="https://github.com/bottlesdevs/Bottles/actions">
    <img src="https://github.com/bottlesdevs/Bottles/workflows/AppImage%20Release/badge.svg">
  </a>
</div>
<br>
<div align="center">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-0.png">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-2.png" width="48%">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-4.png" width="48%">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-3.png">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-3-1.png" width="24%">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-3-2.png" width="24%">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-3-3.png" width="24%">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/master/screenshot-6.png" width="24%">
</div>

## Help Bottles speak your language :speaking_head:
Read [here](https://github.com/bottlesdevs/Bottles/tree/master/po) how to 
translate Bottles in your language or how to help improve existing ones.

## Features
- Create bottles based on environments (a set of rule and dependencies for better software compatibility)
- Access to a customizable environment for all your experiments
- Run every executable (.exe/.msi) in your bottles, using the context menu in your file manager
- Integrated management and storage for executable file arguments
- Support for custom environment variables
- Simplified DLL overrides
- On-the-fly runner change for any Bottle
- Various optimizations for better gaming performance (esync, fsync, dxvk, cache, shader compiler, offload .. and much more.)
- Tweak different wine prefix settings, without leaving Bottles
- Automated dxvk installation
- Automatic installation and management of Wine and Proton runners
- System for checking runner updates for the bottle and automatic repair in case of breakage
- Integrated Dependencies installer with compatibility check based on a community-driver repository
- Detection of installed programs
- Integrated Task manager for wine processes
- Easy access to ProtonDB and WineHQ for support
- Configurations update system across Bottles versions
- Backup bottles as configuration file or full archive
- Import backup archive
- Importer from Bottles v1 (and other wineprefix manager)
- Bottles versioning (experimental)
- .. and much more that you can find by installing Bottles!

### Work in progress
- Installer manager [#55](https://github.com/bottlesdevs/Bottles/issues/55)
- Import backup configuration
- Optional sandboxed bottles

## Install :wrench:
> Disclaimer: This is a development version (alpha), you will find bugs, black 
holes and monsters under the bed. Be careful.

### AppImage :eyes:
This is the official method by which we have chosen to distribute Bottles and it 
is the only one we currently officially support..

Download the latest [Build](https://github.com/bottlesdevs/Bottles/releases/tag/continuous), 
then:
```bash
chmod +x Bottles-devel-x86_64.AppImage
./Bottles-devel-x86_64.AppImage
```
And you're done!

### Unofficial packages
These packages are maitained by our community but not officialy supported.

|Distro|Package Name/Link|Maintainer
|:----:|:----:|:----:|
| Arch Linux | [`bottles-git`](https://aur.archlinux.org/packages/bottles-git) (AUR) | Talebian12 |
| Arch Linux | [`bottles`](https://aur.archlinux.org/packages/bottles) (AUR) | ragouel |
| Tumbleweed | [`bottles`](https://download.opensuse.org/repositories/home:/WhiXard/openSUSE_Tumbleweed/x86_64/)| WhiXard |
| Fedora 33 | [`bottles`](https://download.opensuse.org/repositories/home:/WhiXard/openSUSE_Tumbleweed/x86_64/)| WhiXard |
| Flathub | [`com.usebottles.bottles`](https://github.com/flathub/flathub/pull/2022) | francescomasala |
| Void linux | [`bottles`](https://github.com/void-linux/void-packages/pull/27066) | andry-dev|
| NixOS | [`bottles`](https://github.com/bottlesdevs/Bottles/issues/72) | bloomvdomino |

#### Notices for package maintainers
We are happy to see packaged Bottles but we ask you to respect some small rules:
- The package must be `bottles`, in other distributions it is possible to use suffixes (e.g. `bottles-git` on Arch Linux for the git based package) while on others the RDNN format is required (e.g. `com.usebottles.bottles` on elementary OS and Flathub repository). All other nomenclatures are discouraged.
- In the current development phase, the version corresponds to the formula (`2.commit`, e.g. 2.a005f01), where possible use this formula throughout the development phase. For stable and 'stable development' release you can use the version in the VERSION file and its release. Please don't travel into the future with releases. It might confuse users.
- Do not package external files and do not make changes to the code, no hard script. Obviously with the exception of files essential for packaging.
Once the package is published, you can open a [Pull Request](https://github.com/bottlesdevs/Bottles/pulls) to add it to the packages table above! Thanks :heart:!

### Build with meson :construction_worker:
Instead of use the Appimage you can choose to build your own Bottles from source.

#### Requirements
- meson
- ninja
- python3
- glib
  - `glib2-devel` on Fedora
  - `libglib2.0-dev` on Debian/Ubuntu
  
#### Build
```bash
mkdir build
meson build && cd build
ninja -j$(nproc)
sudo ninja install
```

#### Uninstall
```bash
cd build
sudo ninja uninstall
```

### Flatpak (build)
We provide an initial Flatpak support.  
This is a package not fully tested yet, we don't feel like offering full support.

#### Dependencies
- org.gnome.Sdk
- org.gnome.Sdk.Compat.i386
- org.freedesktop.Sdk.Extension.toolchain-i386

#### Build
```bash
flatpak-builder --repo=bottles --force-clean --user build-dir com.usebottles.bottles.yml
flatpak remote-add --user bottles bottles --no-gpg-verify
flatpak install --user bottles com.usebottles.bottles
```

#### Run
```bash
flatpak run com.usebottles.bottles
```

## Shortcuts
|Shortcut|Action
|:----:|:----:|
| `Ctrl+Q` | Close Bottles |
| `Ctrl+R` | Reload the Bottles list |
| `F1` | Go to the documentation |
| `Esc` | Go back |

## Common issues
There are no other problems. Are we good? 👀

## Why a new application? :baby:
Bottles was born in 2017 as a personal need. I needed a practical way to manage my wineprefixes. 
I hate the idea of using applications that install me a version of wine for each application and 
I decided to create this application, based on the concept of using one or more wine prefixes as 
a "container" for all my applications.

In 2020 thanks to Valve, we have access to Proton. An optimized version of Wine for gaming. 
Thanks also to other projects like DXVK/VKD3D/Esync/Fsync/Shader compiler and others, we can run 
a large set of video games designed for Windows, on Linux.

The idea of creating an environment-based wineprefix manager comes from the standardization of 
dependencies and parameters necessary to run a game. On the other hand, we have software (often 
not up to date) that require environments and configurations different from those used in gaming. 
Hence the idea of managing separate environments.

## Why not just POL or Lutris? :nerd_face:
Because they are similar but different applications. I want to create environments that contain 
more applications and games and where the wine version can be updated.

I also want to be able to export my bottles allowing easy sharing, with or without applications. 
In POL/Lutris we have the concept of "with this version of wine and these changes it works". In 
Bottles the concept is "this is my wine bottle, I want to install this software".

The goal with this version is also to integrate with the system in the best possible way. Being 
able to decide in a few bottles to run an .exe/.msi file and have control over it without having 
to open Bottles for each operation.

Bottles is close to what wineprefix means, since v.2 it provides a simplified method to generate 
environment-based bottles and thanks to other tools it simplifies the management but nothing more.

## Why Appimage? :balloon:
On December 3, 2020 we announced our intentions to migrate to Appimage as the 
official format for Bottles distribution. [Read more](https://github.com/bottlesdevs/Bottles/issues/42).

## Where is Winetricks?! :rage4:
There is not. There will never be. Read [here](https://github.com/bottlesdevs/Bottles/issues/44) our reasons 
and how we want to revolutionize the way we install dependencies in Bottles.

## When? :dizzy_face:
Now. Bottles beta releases are already available, read the Installation section of this file.

## Older versions will be deprecated? :sunglasses:
Maybe in the future, not now.
I will keep both branches updated for a long time.

## Backward compatibility :triumph:
Probably yes. I would like to allow the conversion of the old wine prefixes in v.2. 

Unlike the previous versions, now the bottles are saved with JSON sheets containing all the 
instructions and settings, such as the version of wine/proton in use, the various active flags 
etc.

