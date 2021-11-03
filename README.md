<div align="center">
  <img src="https://raw.githubusercontent.com/bottlesdevs/Bottles/master/data/icons/hicolor/scalable/apps/com.usebottles.bottles.svg" width="64">
  <h1 align="center">Bottles</h1>
  <p align="center">Easily manage wineprefix using environments</p>
</div>

<br/>

<div align="center">
  <a href="https://hosted.weblate.org/engage/bottles">
    <img src="https://hosted.weblate.org/widgets/bottles/-/bottles/svg-badge.svg" />
  </a>
  <a href="https://liberapay.com/bottles">
    <img src="https://img.shields.io/liberapay/receives/bottles.svg?logo=liberapay">
  </a>
  <a href="https://www.codefactor.io/repository/github/bottlesdevs/bottles/overview/master">
    <img src="https://www.codefactor.io/repository/github/bottlesdevs/bottles/badge/master" />
  </a>
  <a href="https://github.com/bottlesdevs/Bottles/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg">
  </a>
  <a href="https://github.com/bottlesdevs/Bottles/actions">
    <img src="https://github.com/bottlesdevs/Bottles/workflows/Build%20release%20packages/badge.svg">
  </a>
  <a href="https://aur.archlinux.org/packages/bottles/">
    <img alt="AUR version" src="https://img.shields.io/aur/version/bottles">
  </a>
  <br>
  <a href="https://t.me/usebottles">
    <img src="https://img.shields.io/static/v1?label=Join%20our&message=Telegram%20Group&color=blue&logo=telegram" />
  </a>
  <a href="https://www.reddit.com/r/usebottles/">
    <img alt="Subreddit subscribers" src="https://img.shields.io/reddit/subreddit-subscribers/usebottles">
  </a>
</div>

<br/>

<div align="center">
  <img src="https://raw.githubusercontent.com/bottlesdevs/Bottles/master/screenshot.png">
</div>

## 📚 Documentation
Before opening a new issue, check if the topic has already been covered 
in our [documentation](https://docs.usebottles.com).

Please note that some pages of the documentation are still being written.

## 🗣 Help Bottles speak your language
Read [here](https://github.com/bottlesdevs/Bottles/tree/master/po#readme) how to 
translate Bottles in your language or how to help improve existing ones.

## 🦾 Features
- Create bottles based on environments (a set of rules and dependencies)
- Access to a customizable environment for all your experiments
- Run every executable (.exe/.msi/.bat) in your bottles, using the context menu in your file manager
- Integrated management and storage for executable file arguments
- Support for custom environment variables
- Simplified DLL overrides
- Manage and install multiple wine/proton/dxvk versions and on-the-fly change
- Various optimizations for better gaming performance (esync, fsync, dxvk, cache, shader compiler, offload ... and much more.)
- Tweak different wine prefix settings, without leaving Bottles
- Automated dxvk installation
- System for checking runner updates for the bottle and automatic repair in case of breakage
- Integrated Dependencies installer with compatibility check based on a community-driver [repository](https://github.com/bottlesdevs/dependencies)
- Detection of installed programs
- Integrated Task manager for wine processes
- Easy access to ProtonDB and WineHQ for support
- Configurations update system across Bottles versions
- Backup and Import bottles from older version and from other managers (Lutris, POL, ..)
- Bottles versioning (experimental)
- ... and much more that you can find by installing Bottles!

### 🚧 Work in progress
- Installer manager [#55](https://github.com/bottlesdevs/Bottles/issues/55)
- Import backup from configuration file
- Optional sandboxed bottles

## ↗️ Install
Bottles is officially provided as AppImage, Flatpak, Snap, AUR, deb package. 
There are also other packages maintained by our community, like Fedora and 
AUR (bottles-git).

Read [here](https://docs.usebottles.com/getting-started/installation) how to
install Bottles on your distribution.

### Notices for package maintainers
We are happy to see packaged Bottles but we ask you to respect some small rules:
- The package must be `bottles`, in other distributions it is possible to use suffixes (e.g. `bottles-git` on Arch Linux for the git based package) while on others the RDNN format is required (e.g. `com.usebottles.bottles` on elementary OS and Flathub repository). All other nomenclatures are discouraged.
- In the current development phase, the version corresponds to the formula (`2.commit`, e.g. 2.a005f01), where possible use this formula throughout the development phase. For stable and 'stable development' release you can use the version in the VERSION file and its release. Please don't travel into the future with releases. It might confuse users.
- Do not package external files and do not make changes to the code, no hard script. Obviously with the exception of files essential for packaging.
Once the package is published, you can open a [Pull Request](https://github.com/bottlesdevs/Bottles/pulls) to add it to the packages table above! Thanks :heart:!

## Shortcuts
|Shortcut|Action
|:----:|:----:|
| `Ctrl+Q` | Close Bottles |
| `Ctrl+R` | Reload the Bottles list |
| `F1` | Go to the documentation |
| `Esc` | Go back |

## FAQ
- [Why Bottles?](https://docs.usebottles.com/faq/why-bottles)
- [Where is Winetricks?](https://docs.usebottles.com/faq/where-is-winetricks)
- [Older versions will be deprecated?](https://docs.usebottles.com/faq/updates-and-old-versions#older-versions-will-be-deprecated)
- [Backward compatibility?](https://docs.usebottles.com/faq/updates-and-old-versions#backward-compatibility)
