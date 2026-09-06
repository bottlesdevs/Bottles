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
- [DAILY JEWELS BLITZ MAHJONG](https://studyplaying.github.io/daily-jewels-blitz-mahjong.html)
- [TAPKO](https://studyplayings.web.app/tapko.html)
- [CATEGORY CONTROLLER](https://studyquests.pages.dev/category-controller.html)
- [BOBBLEHEAD BALL](https://themindplay.pages.dev/bobblehead-ball.html)
- [WOLF LIFE SIMULATOR](https://themindplaying.web.app/wolf-life-simulator.html)
- [BRIDGE WARS](https://themindplaying.web.app/bridge-wars.html)
- [CATEGORY INCREMENTAL388](https://thelearnquesters.pages.dev/category-incremental388.html)
- [CATEGORY DRESS UP](https://studyplayings.pages.dev/category-dress-up.html)
- [CROWD EVOLUTION](https://thelearnquesters.pages.dev/crowd-evolution.html)
- [SLOPE EMOJI 2](https://themindplaying.web.app/slope-emoji-2.html)
- [IDLE RESTAURANT TYCOON](https://studyquesthub.web.app/idle-restaurant-tycoon.html)
- [PLANT GIRL DEFENSE ZOMBIE](https://themindplay.pages.dev/plant-girl-defense-zombie.html)
- [NONOGRAM DAILY](https://themindplay.pages.dev/nonogram-daily.html)
- [MAFIA SNIPER CRIME SHOOTING](https://quizverses-9d2f2.web.app/mafia-sniper-crime-shooting.html)
- [MERGE SESAME](https://themindplaying.web.app/merge-sesame.html)
- [KINGDOM PUZZLES](https://learnquester.github.io/kingdom-puzzles.html)
- [CATEGORY ONE BUTTON84](https://quizverses.github.io/category-one-button84.html)
- [CATEGORY COOKING](https://thelearnquesters.pages.dev/category-cooking.html)
- [DTA BEST THIEF](https://themindplay.pages.dev/dta-best-thief.html)
- [MIRACLE MAHJONG](https://thelearnquesters.pages.dev/miracle-mahjong.html)
- [DIGWORM IO](https://themindplaying.web.app/digworm-io.html)
- [BANK ROBBERY ESCAPE](https://quizverses.github.io/bank-robbery-escape.html)
- [QUACKVENTURE](https://themindplay.pages.dev/quackventure.html)
- [INDEX15](https://themindplays.pages.dev/index15.html)
- [DUCKLINGS](https://quizverses.github.io/ducklings.html)
- [BOXTERIA](https://themindplay.pages.dev/boxteria.html)
- [KNOCK AND RUN 100 DOORS ESCAPE](https://themindplaying.web.app/knock-and-run-100-doors-escape.html)
- [THUMBPINBALL](https://themindplays.pages.dev/thumbpinball.html)
- [CATEGORY MAKEUP51](https://thelearnquesters.pages.dev/category-makeup51.html)
- [COLORS PINS](https://studyplayings.pages.dev/colors-pins.html)
- [CATEGORY MERGE GAMES](https://skillplay.github.io/category-merge-games.html)
- [JUNGLE MATCH ADVENTURES](https://themindplays.pages.dev/jungle-match-adventures.html)
- [WHEEL OF BINGO](https://learnquester.github.io/wheel-of-bingo.html)
- [CURSED TREASURE 11 2](https://themindskillplayplay.pages.dev/cursed-treasure-11-2.html)
- [INDEX29](https://themindskillplayplay.pages.dev/index29.html)
- [WORDS WITH PROF WISELY](https://skillplay.github.io/words-with-prof-wisely.html)
- [TRALALA CONNECT](https://quizverses.github.io/tralala-connect.html)
- [FANTASY MADNESS](https://themindplays.pages.dev/fantasy-madness.html)
- [MEMOJI](https://themindplays.pages.dev/memoji.html)
- [MAHJONG MAGIC ISLANDS](https://learnquester.github.io/mahjong-magic-islands.html)
- [STICKMAN BATTLE 1 4 PLAYERS](https://studyquests.github.io/stickman-battle-1-4-players.html)
- [SUPER CLONER 3D](https://themindplays.pages.dev/super-cloner-3d.html)
- [PARKOUR WORLD 2](https://quizverses.github.io/parkour-world-2.html)
- [BUBBLE UP](https://skillplay.github.io/bubble-up.html)
- [CAP](https://learnquester.github.io/cap.html)
- [LOL FUNNY DANCE](https://learnquester.github.io/lol-funny-dance.html)
- [REVOXEL 3D VOXEL RPG SHOOTER](https://studyplayings.pages.dev/revoxel-3d-voxel-rpg-shooter.html)
- [SNOW BALL RACING MUTLIPLAYER](https://thelearnquesters.pages.dev/snow-ball-racing-mutliplayer.html)
- [ARCHERS RAGDOLL PHYSICS](https://skillplay.github.io/archers-ragdoll-physics.html)
- [STUNT CAR EXTREME 2](https://studyquests.github.io/stunt-car-extreme-2.html)
- [COLOR NONOGRAM PUZZLE](https://skillplay.github.io/color-nonogram-puzzle.html)
- [BELL MADNESS](https://themindplay.pages.dev/bell-madness.html)
- [DYNAMONS 8](https://themindplay.pages.dev/dynamons-8.html)
- [CATEGORY UNBLOCKED WEBSITES](https://studyquests.github.io/category-unblocked-websites.html)
- [OFFLINE FPS ROYALE](https://studyplayings.pages.dev/offline-fps-royale.html)
- [FASHION FAMOUS](https://skillplay.github.io/fashion-famous.html)
- [99 BALLS](https://themindplay.pages.dev/99-balls.html)
- [HALLOWEEN STICKMAN](https://iskillplay.web.app/halloween-stickman.html)
- [CAT ESCAPE](https://iskillplay.web.app/cat-escape.html)
- [CATEGORY CASUAL 14](https://studyplaying.github.io/category-casual-14.html)
- [PUPPY MERGE](https://iskillplay.web.app/puppy-merge.html)
- [CANDY COLOR SORT PUZZLE](https://themindplaying.web.app/candy-color-sort-puzzle.html)
- [COLOR BLOCK JAM](https://iskillplay.web.app/color-block-jam.html)
- [ASMR MAKEOVER MAKEUP STUDIO](https://quizverses.github.io/asmr-makeover-makeup-studio.html)
- [BILLIARDS 3D RUSSIAN PYRAMID](https://themindplaying.web.app/billiards-3d-russian-pyramid.html)
- [JAILBREAK ASSAULT](https://learnquester.github.io/jailbreak-assault.html)
- [CANDY MONSTER RAFFI](https://skillplay.github.io/candy-monster-raffi.html)
- [GLOVES GROW RUSH](https://skillplay.github.io/gloves-grow-rush.html)
- [ARROW SURVIVAL 15 SECONDS](https://themindplay.pages.dev/arrow-survival-15-seconds.html)
- [BLOCK TEAM DEATHMATCH](https://skillplay.github.io/block-team-deathmatch.html)
- [STICKMAN ESCAPES FROM PRISON](https://iskillplay.web.app/stickman-escapes-from-prison.html)
- [ARROW ESCAPE](https://themindplay.pages.dev/arrow-escape.html)
- [CATEGORY ADVENTURE 3](https://themindplays.pages.dev/category-adventure-3.html)
- [SUIKA KAWAII CAT MERGE GAME](https://studyquests.pages.dev/suika-kawaii-cat-merge-game.html)
- [QUIZMANIA TRIVIA GAME](https://studyquests.github.io/quizmania-trivia-game.html)
- [INDEX13](https://learnquester.github.io/index13.html)
- [LABUBU MERGE](https://themindplay.pages.dev/labubu-merge.html)
- [BUBBLE SORTING INFINITE REMASTERED](https://themindplays.pages.dev/bubble-sorting-infinite-remastered.html)
- [RIFT OF HELL DEMONS WAR](https://themindplaying.web.app/rift-of-hell-demons-war.html)
- [MERGE FELLAS ONLINE](https://themindplaying.web.app/merge-fellas-online.html)
- [TICTOC URBAN OUTFITS](https://studyplaying.github.io/tictoc-urban-outfits.html)
- [IDLE POP MERGE](https://themindplay.pages.dev/idle-pop-merge.html)
- [COLORWARSIO](https://skillplay.github.io/colorwarsio.html)
- [HEAD JUMP](https://quizverses.github.io/head-jump.html)
- [THE SURVEY](https://quizverses.github.io/the-survey.html)
- [GUN FEST](https://iskillplay.web.app/gun-fest.html)
- [BUBBLE SHOOTER FREE 3](https://studyquests.github.io/bubble-shooter-free-3.html)
- [AUTUMN GLAM GALA](https://skillplay.github.io/autumn-glam-gala.html)
- [FISHING LIFE](https://themindplay.pages.dev/fishing-life.html)
- [ROPE KING](https://themindplays.pages.dev/rope-king.html)
- [DOOMSDAY ZOMBIE TD](https://quizverses-9d2f2.web.app/doomsday-zombie-td.html)
- [DART HERO](https://studyplayings.pages.dev/dart-hero.html)
- [CATEGORY ART](https://studyplaying.github.io/category-art.html)
- [REAL RACING 3D](https://iskillplay.web.app/real-racing-3d.html)
- [CATEGORY BOARDGAMES](https://learnquesters.pages.dev/category-boardgames.html)
- [LAST UFO DEFENSE](https://quizverses.github.io/last-ufo-defense.html)
- [UNCLE HIT PUNCH THE DUMMY](https://skillplay.github.io/uncle-hit-punch-the-dummy.html)
- [DTA BEST THIEF](https://learnquester.github.io/dta-best-thief.html)
- [GAL SLIDING PUZZLE](https://skillplay.github.io/gal-sliding-puzzle.html)
- [GUNS VS MAGIC](https://thelearnquester.web.app/guns-vs-magic.html)
- [SOUL NOT FOUND](https://learnquester.github.io/soul-not-found.html)
- [INDEX26](https://themindplays.pages.dev/index26.html)
- [LOLLIPOP STACK RUN](https://studyquests.github.io/lollipop-stack-run.html)
- [ECO BLOCK PUZZLE](https://themindplaying.web.app/eco-block-puzzle.html)
- [FOOD TOWER DEFENSE](https://themindplays.pages.dev/food-tower-defense.html)
- [EPIC CAR STUNT RACE OBBY](https://studyplaying.github.io/epic-car-stunt-race-obby.html)
- [SHADOW STICKMAN FIGHT](https://skillplay.github.io/shadow-stickman-fight.html)
- [SUPERMARKET SORT GROCERY GAME](https://quizverses.github.io/supermarket-sort-grocery-game.html)
- [BUS DRIVER](https://iskillplay.web.app/bus-driver.html)
- [BUS STOP COLOR JAM](https://thelearnquester.web.app/bus-stop-color-jam.html)
- [STARRY STYLE DORAMA OF DREAM](https://iskillplay.web.app/starry-style-dorama-of-dream.html)
- [CATEGORY ANIMAL](https://skillplay.github.io/category-animal.html)
- [CATEGORY PUZZLE 2](https://studyplayings.web.app/category-puzzle-2.html)
- [BUBBLE SHOOTER BLAST](https://iskillplay.web.app/bubble-shooter-blast.html)
- [SAVE MY PET](https://thelearnquesters.pages.dev/save-my-pet.html)
- [DYE IT RIGHT COLOR PICKER](https://themindskillplayplay.pages.dev/dye-it-right-color-picker.html)
- [SWEET MATCH](https://themindplaying.web.app/sweet-match.html)
- [FOREST TILES](https://studyplayings.web.app/forest-tiles.html)
- [INDEX11](https://themindplays.pages.dev/index11.html)
- [ECHOLOCATION SHOOTER](https://quizverses.pages.dev/echolocation-shooter.html)
- [SWORD LIFE](https://skillplay.github.io/sword-life.html)
- [SHAPE TRANSFORMING SHIFTING RUN](https://studyplaying.github.io/shape-transforming-shifting-run.html)
- [TOWER WARS ARENA](https://quizverses-9d2f2.web.app/tower-wars-arena.html)
- [INCREDIBLE PRINCESSES AND VILLAINS PUZZLE](https://skillplay.github.io/incredible-princesses-and-villains-puzzle.html)
- [FARM BUSINESS SAGA](https://quizverses-9d2f2.web.app/farm-business-saga.html)
- [MY FARM EMPIRE](https://themindplay.pages.dev/my-farm-empire.html)
- [INDEX5](https://studyplaying.github.io/index5.html)
- [MOJICON WINTER CONNECT](https://themindplaying.web.app/mojicon-winter-connect.html)
- [CATEGORY COLOR197](https://skillplay.github.io/category-color197.html)
- [XYTRIAN RUNNER](https://studyquests.github.io/xytrian-runner.html)
