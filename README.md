<div align="center">
  <img src="https://i.imgur.com/hFokdsQ.png" width="64">
  <h1 align="center">Bottles</h1>
  <p align="center">Easily manage wineprefix</p>
</div>

<br/>

<p align="center">
  <a href="https://appcenter.elementary.io/com.github.mirkobrombin.bottles">
    <img src="https://appcenter.elementary.io/badge.svg" alt="Get it on AppCenter">
  </a>
</p>

<br/>

<div align="center">
   <a href="https://git.mirko.pm/brombinmirko/Bottles/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg">
   </a>
</div>

<div align="center">
    <img  src="https://git.mirko.pm/brombinmirko/Bottles/raw/master/data/screenshot-1.png"> <br>
    <img  src="https://git.mirko.pm/brombinmirko/Bottles/raw/master/data/screenshot-2.png"> <br>
    <img  src="https://git.mirko.pm/brombinmirko/Bottles/raw/master/data/screenshot-3.png"> <br>
    <img  src="https://git.mirko.pm/brombinmirko/Bottles/raw/master/data/screenshot-4.png">
</div>

## Problems/New Features?
Read the [Wiki](https://git.mirko.pm/brombinmirko/Bottles/wikis).  
In any case, ask for support [here](https://git.mirko.pm/brombinmirko/Bottles/issues).

## Requirements
- wine-stable
- xterm
- python3

## How to run
```bash
com.github.mirkobrombin.bottles
```

## Known bugs
- Console logs are not translated

## Languages coming soon
- Chinese
- Indian

## Installation

### From AppCenter (elementary OS users)
Go to the [AppCenter](https://appcenter.elementary.io/com.github.mirkobrombin.bottles") page.

### From .deb package
Grab an updated release [here](https://github.com/mirkobrombin/Bottles/releases), then install:

```bash
sudo dpkg -i com.github.mirkobrombin.bottles_*.deb
```

### From .setup.py
Download the updated source [here](https://git.mirko.pm/brombinmirko/Bottles/archive/master.zip), or use git:

```bash
git clone https://git.mirko.pm/brombinmirko/Bottles.git
cd Bottles
sudo python3 setup.py install
```

### From PPA (may be out of date)
Configure PPA:
```bash
curl -s --compressed "https://linuxhubit.github.io/ppa/KEY.gpg" | sudo apt-key add -
sudo curl -s --compressed -o /etc/apt/sources.list.d/my_list_file.list "https://linuxhubit.github.io/ppa/my_list_file.list"
sudo apt update
```
then install:
```bash
sudo apt install com.github.mirkobrombin.bottles
```


