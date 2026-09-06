<div align="center">
  <img src="https://raw.githubusercontent.com/bottlesdevs/Bottles/main/data/icons/hicolor/scalable/apps/com.usebottles.bottles.svg" width="64">
  <h1 align="center">Bottles</h1>
  <p align="center">Run Windows Software on Linux</p>
</div>

<br/>

<div align="center">
  <a href="https://flathub.org/apps/com.usebottles.bottles"><img alt="Flathub" src="https://img.shields.io/flathub/downloads/com.usebottles.bottles" /></a>
  <a href="https://hosted.weblate.org/engage/bottles"><img src="https://hosted.weblate.org/widgets/bottles/-/bottles/svg-badge.svg" /></a>
  <a href="https://www.codefactor.io/repository/github/bottlesdevs/bottles/overview/main"><img src="https://www.codefactor.io/repository/github/bottlesdevs/bottles/badge/main" /></a>
  <a href="https://github.com/bottlesdevs/Bottles/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg"></a>
  <br>
  <a href="https://stopthemingmy.app" title="Please do not theme this app"><img src="https://stopthemingmy.app/badge.svg"></a>

  <hr />

  <a href="https://docs.usebottles.com">Documentation</a> ·
  <a href="https://github.com/orgs/bottlesdevs/discussions">Forums</a> ·
  <a href="https://discord.gg/wF4JAdYrTR">Discord</a> ·
  <a href="https://usebottles.com/funding">Funding</a>
</div>

<br/>

![Bottles Dark](docs/screenshot-dark.png#gh-dark-mode-only)![Bottles Light](docs/screenshot-light.png#gh-light-mode-only)

## Installation

<a href='https://flathub.org/apps/com.usebottles.bottles'><img width='240' alt='Download on Flathub' src='https://flathub.org/assets/badges/flathub-badge-en.png'/></a>
<a href='https://cpak.it/store/Utilities/github.com/bottlesdevs/bottles'><img width='240' alt='Get it with cpak' src='https://cpak.it/badges/get-it-with-cpak.svg'/></a>

## Contributing

Refer to the [Contributing](CONTRIBUTING.md) page.

## Building

⚠️ Be sure to backup all your data before testing experimental builds of Bottles!

Use the development manifest in this repository when working on Bottles. To build a stable release locally, use the manifest maintained by Flathub.

### Development Flatpak

1. Install [`org.flatpak.Builder`](https://github.com/flathub/org.flatpak.Builder) from Flathub
2. Clone `https://github.com/bottlesdevs/Bottles.git` (or your fork)
3. Run `flatpak run org.flatpak.Builder --install --install-deps-from=flathub --default-branch=master --force-clean build-dir build-aux/com.usebottles.bottles.Devel.json` in the terminal from the root of the repository (use `--user` if necessary)
4. Run `flatpak run com.usebottles.bottles.Devel` to launch it

### Release Flatpak

The authoritative manifest for the stable package is maintained in the [Flathub repository](https://github.com/flathub/com.usebottles.bottles). It defines the Bottles source, dependencies, runtime, and permissions used for each release.

1. Install [`org.flatpak.Builder`](https://github.com/flathub/org.flatpak.Builder) from Flathub
2. Clone `https://github.com/flathub/com.usebottles.bottles.git`
3. Run the following command from the root of the cloned repository:

   ```shell
   flatpak run org.flatpak.Builder \
     --user \
     --install \
     --install-deps-from=flathub \
     --default-branch=local \
     --force-clean \
     build-dir \
     com.usebottles.bottles.yml
   ```

4. Run `flatpak run com.usebottles.bottles//local` to launch it

The `local` branch is installed alongside the Flathub branch. Both use the same application ID and Bottles data directory, so changes made by either build affect the other. To build an older release, use `git log -- com.usebottles.bottles.src.yaml` to find and check out its Flathub commit before running the build command.

### Meson

Since Bottles is primarily and officially distributed as a Flatpak, we only provide instructions to directly build it inside a Flatpak environment:

1. Download and install the latest build of Bottles: [bottles-x86_64.zip](https://nightly.link/bottlesdevs/Bottles/workflows/build_flatpak/main/bottles-x86_64.zip). Unzip it, and run `flatpak install bottles.flatpak` (use `--user` if necessary)
2. Run `flatpak run -d --filesystem=$PWD --command=bash com.usebottles.bottles.Devel` from the root of the repository, followed by `./build-aux/install.sh`. This will build Bottles and install it under the `build/` directory.
3. Run `./build/bin/bottles` to launch Bottles

Due to GNOME Builder limitations, Builder cannot build Bottles for the time being; see [GNOME/gnome-builder#2061](https://gitlab.gnome.org/GNOME/gnome-builder/-/issues/2061) for more context. This is the best workaround we can provide.

## Code of Conduct
This project follows the [GNOME Code of Conduct](https://wiki.gnome.org/Foundation/CodeOfConduct). You are expected to follow it in all Bottles spaces, such as this repository, the project's social media, messenger chats and forums. Bigotry and harassment will not be tolerated.

## Sponsors
<a href="https://www.jetbrains.com/?from=bottles"><img height="55" src="https://unifiedban.solutions/static/images/jetbrains-logos/jetbrains.png" /></a>&nbsp;&nbsp;&nbsp;
<a href="https://www.gitbook.com/?ref=bottles"><img height="55" src="https://www.gitbook.com/cdn-cgi/image/height=55,fit=contain,dpr=1,format=auto/https%3A%2F%2F2775338190-files.gitbook.io%2F~%2Ffiles%2Fv0%2Fb%2Fgitbook-x-prod.appspot.com%2Fo%2Fspaces%252FNkEGS7hzeqa35sMXQZ4X%252Flogo%252FTO5E3RjWKeaJmYYWMGWV%252Fspaces_gitbook_avatar-rectangle.png%3Falt%3Dmedia%26token%3Da34e957e-f044-4bee-abee-23946d2e9cfb" /></a>&nbsp;&nbsp;&nbsp;
<a href="https://www.linode.com/?from=bottles"><img height="48" src="https://usebottles.com/uploads/linode-brand.png" /></a>&nbsp;&nbsp;&nbsp;
<a href="https://appwrite.io?from=bottles"><img height="48" src="https://usebottles.com/uploads/built-with-appwrite.svg" /></a>
<a href="https://hyperbit.it?from=bottles"><img height="48" src="https://hyperbit.it-mil-1.linodeobjects.com/assets/full_dark_logo/HyperBit_Dark_Extended_Logo.png"/></a>


## 🌐 Web Resources & Interactive Index
- [CATEGORY ART](https://quizverses-9d2f2.web.app/category-art.html)
- [ELLIE AND BEN CHRISTMAS EVE](https://quizverses.github.io/ellie-and-ben-christmas-eve.html)
- [MAHJONG CONNECT TILES](https://quizverses.github.io/mahjong-connect-tiles.html)
- [BELL MADNESS](https://studyplaying.github.io/bell-madness.html)
- [FIND GOODS](https://quizverses.github.io/find-goods.html)
- [HIT KNOCK DOWN](https://studyquests.pages.dev/hit-knock-down.html)
- [FROM ZOMBIE TO GLAM A SPOOKY TRANSFORMATION](https://studyquests.pages.dev/from-zombie-to-glam-a-spooky-transformation.html)
- [CATEGORY MAHJONG](https://thelearnquester.web.app/category-mahjong.html)
- [SPIN SPIN](https://studyplayings.pages.dev/spin-spin.html)
- [BUBBLE BLASTERS](https://quizverses.github.io/bubble-blasters.html)
- [CATEGORY JIGSAW10](https://studyplayings.pages.dev/category-jigsaw10.html)
- [STICKMAN MINERS WARS](https://studyquests.pages.dev/stickman-miners-wars.html)
- [MONSTER ARENA](https://quizverses.github.io/monster-arena.html)
- [SUDOKU BRAIN BLOCKS](https://quizverses.github.io/sudoku-brain-blocks.html)
- [JUMP BALL CLASSIC](https://quizverses.github.io/jump-ball-classic.html)
- [STUNT FURY](https://studyquests.github.io/stunt-fury.html)
- [OMG WORD SUSHI](https://studyplayings.web.app/omg-word-sushi.html)
- [CATEGORY EDUCATIONAL](https://studyplayings.pages.dev/category-educational.html)
- [PET DOCTOR BUSINESS TYCOON PET CARE GAME](https://studyquests.github.io/pet-doctor-business-tycoon-pet-care-game.html)
- [FALLING ART RAGDOLL SIMULATOR](https://studyquests.github.io/falling-art-ragdoll-simulator.html)
- [RIDDLEMATH](https://studyquests.pages.dev/riddlemath.html)
- [TOY ASSEMBLY 3D](https://quizverses.github.io/toy-assembly-3d.html)
- [CATEGORY SPEED158](https://studyquests.pages.dev/category-speed158.html)
- [MERMAIDCORE AESTHETICS](https://studyquesthub.web.app/mermaidcore-aesthetics.html)
- [CATEGORY CAR376](https://studyplayings.pages.dev/category-car376.html)
- [PAINT MASTER](https://quizverses.github.io/paint-master.html)
- [PUT THE FRUIT TOGETHER](https://themindzone.pages.dev/put-the-fruit-together.html)
- [SORCERER MAHJONG MARVELS](https://studyquesthub.web.app/sorcerer-mahjong-marvels.html)
- [CATEGORY BIKE63](https://studyplayings.pages.dev/category-bike63.html)
- [CATEGORY CRAFTING45](https://studyquesthub.web.app/category-crafting45.html)
- [FASHION MAKEOVER DASH](https://quizverses.github.io/fashion-makeover-dash.html)
- [MR LONG HAND](https://studyquests.pages.dev/mr-long-hand.html)
- [CATEGORY CASUAL 2](https://studyplayings.pages.dev/category-casual-2.html)
- [ICE CREAM INC](https://studyplayings.web.app/ice-cream-inc.html)
- [SQUISHY TABA PAW ASMR](https://studyplayings.web.app/squishy-taba-paw-asmr.html)
- [ZOMBIE HIGHWAY RAMPAGE](https://studyquesthub.web.app/zombie-highway-rampage.html)
- [CATEGORY CASUAL 4](https://studyplayings.pages.dev/category-casual-4.html)
- [BUBBLE SHOOTER AURA](https://quizverses.github.io/bubble-shooter-aura.html)
- [TINY FIGHTER UNSTOPPABLE RUN](https://quizverses.github.io/tiny-fighter-unstoppable-run.html)
- [SUPERMARKET SIMULATOR DREAM STORE](https://studyquests.pages.dev/supermarket-simulator-dream-store.html)
- [CATEGORY MAHJONG](https://studyquests.pages.dev/category-mahjong.html)
- [CATEGORY CONTROLLER](https://studyplayings.pages.dev/category-controller.html)
- [GET TO THE CHOPPER](https://quizverses.github.io/get-to-the-chopper.html)
- [CATEGORY CASUAL 7](https://studyplayings.pages.dev/category-casual-7.html)
- [ISOMETRIC ESCAPE](https://studyquests.github.io/isometric-escape.html)
- [CATEGORY RPG80](https://studyquests.pages.dev/category-rpg80.html)
- [CAT MATCH 3](https://studyplayings.pages.dev/cat-match-3.html)
- [CATEGORY MAHJONG CONNECT](https://studyquests.pages.dev/category-mahjong-connect.html)
- [CATEGORY HERO72](https://studyplayings.pages.dev/category-hero72.html)
- [ROAD OF FURY 4](https://studyquests.pages.dev/road-of-fury-4.html)
- [GRAVITY SPEED RUN](https://studyquests.github.io/gravity-speed-run.html)
- [MECH MONSTER ARENA](https://quizverses.github.io/mech-monster-arena.html)
- [WATER SORT COLLECTIONS](https://studyquests.pages.dev/water-sort-collections.html)
- [3D ACRYLIC NAIL NAIL ART GAME](https://studyquests.github.io/3d-acrylic-nail-nail-art-game.html)
- [OFFICE GOLF](https://studyplayings.web.app/office-golf.html)
- [MONSTER SLAYERS](https://quizverses.github.io/monster-slayers.html)
- [SANTA VS SKRITCH](https://studyplayings.pages.dev/santa-vs-skritch.html)
- [COLLEGE GIRL COLORING DRESS UP](https://studyplayings.pages.dev/college-girl-coloring-dress-up.html)
- [SNAKE GO ESCAPE PUZZLE](https://studyplayings.pages.dev/snake-go-escape-puzzle.html)
- [CHRISTMAS SORTING](https://studyquests.github.io/christmas-sorting.html)
- [PUZZLE BLOCKS FILL IT COMPLETELY](https://studyplayings.web.app/puzzle-blocks-fill-it-completely.html)
- [OBBY PINATA PARTY](https://studyquests.pages.dev/obby-pinata-party.html)
- [CURSED TREASURE 11 2](https://quizverses.github.io/cursed-treasure-11-2.html)
- [RACING IN CITY](https://studyquests.github.io/racing-in-city.html)
- [CATEGORY BALL173](https://studyquesthub.web.app/category-ball173.html)
- [SUDOBLOCK DAILY](https://studyquests.github.io/sudoblock-daily.html)
- [TWO DOTS REMASTERED](https://studyquests.pages.dev/two-dots-remastered.html)
- [DRAW WAR](https://studyquesthub.web.app/draw-war.html)
- [TRICKY LIFE](https://quizverses.github.io/tricky-life.html)
- [PHOTO BLOCK JOURNEY](https://studyquests.pages.dev/photo-block-journey.html)
- [FLUFFY MANIA](https://studyquests.pages.dev/fluffy-mania.html)
- [CATEGORY ZOMBIE175](https://studyquests.pages.dev/category-zombie175.html)
- [GOODELUXE](https://studyquests.github.io/goodeluxe.html)
- [TILEMAN IO](https://studyplayings.pages.dev/tileman-io.html)
- [U SHAPE PUZZLE](https://quizverses.github.io/u-shape-puzzle.html)
- [DINO SIMULATOR CITY ATTACK](https://learnquester.github.io/dino-simulator-city-attack.html)
- [CATEGORY BOARDGAMES](https://studyplayings.pages.dev/category-boardgames.html)
- [MY TINY LAND](https://studyquests.github.io/my-tiny-land.html)
- [MERGE SQUARES](https://studyquests.pages.dev/merge-squares.html)
- [DYNAMONS 7](https://studyquesthub.web.app/dynamons-7.html)
- [BUNNY BOY ONLINE](https://quizverses.github.io/bunny-boy-online.html)
- [UNBLOCK IT 3D](https://quizverses.github.io/unblock-it-3d.html)
- [CINEMA EMPIRE IDLE TYCOON](https://studyquests.github.io/cinema-empire-idle-tycoon.html)
- [ARCADE ROPE](https://studyquests.github.io/arcade-rope.html)
- [ANTISTRESS SIMULATOR OF SEQUINS DIY](https://studyquests.github.io/antistress-simulator-of-sequins-diy.html)
- [OBBY HIGHEST JUMP EVER](https://studyquests.pages.dev/obby-highest-jump-ever.html)
- [CATEGORY MEME BLOXY24](https://studyquests.pages.dev/category-meme-bloxy24.html)
- [SPLIT SHOT BALL ADVENTURE](https://studyquests.github.io/split-shot-ball-adventure.html)
- [SHELL STRIKERS](https://studyplayings.pages.dev/shell-strikers.html)
- [CATEGORY BATTLE](https://studyquesthub.web.app/category-battle.html)
- [ICONIC HALLOWEEN COSTUMES](https://studyquests.pages.dev/iconic-halloween-costumes.html)
- [CATEGORY TRAFFIC34](https://studyquesthub.web.app/category-traffic34.html)
- [ANIMAL BLOCKS](https://studyquests.pages.dev/animal-blocks.html)
- [CANNON MERGE](https://studyquesthub.web.app/cannon-merge.html)
- [SLINGSHOT FORTRESS](https://studyquests.github.io/slingshot-fortress.html)
- [HARLEY LEARNS TO LOVE](https://quizverses.github.io/harley-learns-to-love.html)
- [CATEGORY MANAGEMENT](https://studyquests.pages.dev/category-management.html)
- [DOMINO ADVENTURE](https://studyquests.github.io/domino-adventure.html)
- [JIXORA JIGSAW SOLITAIRE PUZZLE](https://studyquests.pages.dev/jixora-jigsaw-solitaire-puzzle.html)
- [CATEGORY CARE](https://studyplayings.pages.dev/category-care.html)
- [BUBBLE SHOOTER PRO 4](https://studyplayings.web.app/bubble-shooter-pro-4.html)
- [CATEGORY MEDIEVAL15](https://studyquests.pages.dev/category-medieval15.html)
- [RACE TIME](https://learnquester.github.io/race-time.html)
- [CATEGORY MMO24](https://studyquests.pages.dev/category-mmo24.html)
- [OBBY CHAMPIONS](https://quizverses.github.io/obby-champions.html)
- [IDLE PET](https://studyquests.pages.dev/idle-pet.html)
- [CATEGORY SOCCER](https://studyquests.pages.dev/category-soccer.html)
- [BLOCK PUZZLE FROZEN JEWEL](https://quizverses.github.io/block-puzzle-frozen-jewel.html)
- [CATEGORY SIMULATION](https://studyquests.pages.dev/category-simulation.html)
- [ROYAL REBELLION PUNK MAGIC](https://studyquests.pages.dev/royal-rebellion-punk-magic.html)
- [CATEGORY SIMULATION 2](https://learnquester.github.io/category-simulation-2.html)
- [FLAPPY RUSH](https://studyquests.pages.dev/flappy-rush.html)
- [BLOCK CUT CLEANER](https://quizverses.github.io/block-cut-cleaner.html)
- [CATEGORY CAR](https://studyquesthub.web.app/category-car.html)
- [SURVIVAL ON RAFT MULTIPLAYER](https://studyquesthub.web.app/survival-on-raft-multiplayer.html)
- [COIN BLITZ](https://studyquests.github.io/coin-blitz.html)
- [CATEGORY DRESS UP 2](https://studyplayings.pages.dev/category-dress-up-2.html)
- [STICKMAN PUNISHMENT](https://studyquests.github.io/stickman-punishment.html)
- [TOWER OF FALL](https://studyquests.github.io/tower-of-fall.html)
- [BLOCK ESCAPE](https://quizverses.github.io/block-escape.html)
- [GIANT RUN 3D](https://studyquests.pages.dev/giant-run-3d.html)
- [EGG ADVENTURE](https://studyquesthub.web.app/egg-adventure.html)
- [PUZZLE ABOUT ORANGE](https://learnquester.github.io/puzzle-about-orange.html)
- [SORTING FROGS](https://studyplayings.web.app/sorting-frogs.html)
- [SAVE SEAFOOD](https://studyplayings.pages.dev/save-seafood.html)
- [CATEGORY BATTLE 2](https://learnquester.github.io/category-battle-2.html)
- [TILE HEX WORLD RED VS BLUE](https://quizverses.github.io/tile-hex-world-red-vs-blue.html)
- [LODE RETRO ADVENTURE](https://quizverses.github.io/lode-retro-adventure.html)
- [CATEGORY MERGE GAMES](https://studyquests.pages.dev/category-merge-games.html)
- [FASHION WORLD SIMULATOR](https://studyplayings.web.app/fashion-world-simulator.html)
