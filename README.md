<div align="center">
  <img src="https://i.imgur.com/hFokdsQ.png" width="64">
  <h1 align="center">Bottles (v.2)</h1>
  <p align="center">Easily manage wineprefix using environments</p>
  <small>⚠️ This version is under development. <a href="https://github.com/bottlesdevs/Bottles/tree/v1">Here</a> you can find the stable v1.</small>
</div>

<br/>

<div align="center">
   <a href="https://gitlocalize.com/repo/5547/whole_project?utm_source=badge">
    <img src="https://gitlocalize.com/repo/5547/whole_project/badge.svg" /> 
   </a>
   <a href="https://git.mirko.pm/brombinmirko/Bottles/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg">
   </a>
   <a href="https://travis-ci.com/github/bottlesdevs/Bottles">
    <img src="https://travis-ci.com/bottlesdevs/Bottles.svg?branch=develop">
   </a>
  <a href="https://github.com/bottlesdevs/Bottles/actions">
    <img src="https://github.com/bottlesdevs/Bottles/workflows/AppImage/badge.svg">
  </a>
</div>

<div align="center">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/develop/screenshot-0.png" width="300">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/develop/screenshot-1-1.png" width="300">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/develop/screenshot-2.png" width="300">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/develop/screenshot-3.png" width="300">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/develop/screenshot-3-1.png" width="300">
    <img  src="https://raw.githubusercontent.com/mirkobrombin/Bottles/develop/screenshot-9.png" width="300">
</div>

## Install
> Disclaimer: This is a development version (alpha), you will find bugs, black holes and monsters under the bed. Be careful.
### AppImage

Download the latest [Build](https://github.com/bottlesdevs/Bottles/releases/tag/continuous)

```
cd Downloads
chmod +x Bottles-commit-x86_64.AppImage
./Bottles-commit-x86_64.AppImage
And you're done!
```

### Build with meson
Instead of use the Appimage you can choose to build your own Bottles from source.

#### Requirements
```
- meson
- ninja
- python3
```

#### Build
```
mkdir build
meson build && cd build
ninja -j$(nproc)
sudo ninja install
```

## Why a new application?
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

## Why not just POL or Lutris?
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

## Why Appimage?
On December 3, 2020 we announced our intentions to migrate to Appimage as the official format for Bottles distribution. [Read more](https://github.com/bottlesdevs/Bottles/issues/42).

## When?
Idk. Really. Keep an eye on the develop branch, sooner or later there will be an almost stable 
release

## Older versions will be deprecated?
Maybe in the future, not now.
I will keep both branches updated for a long time.

## Backward compatibility
Probably yes. I would like to allow the conversion of the old wine prefixes in v.2. 

Unlike the previous versions, now the bottles are saved with JSON sheets containing all the 
instructions and settings, such as the version of wine/proton in use, the various active flags 
etc.
