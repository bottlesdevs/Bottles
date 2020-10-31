<div align="center">
  <img src="https://i.imgur.com/hFokdsQ.png" width="64">
  <h1 align="center">Bottles</h1>
  <p align="center">Easily manage wineprefix</p>
</div>

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

### From PPA
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


