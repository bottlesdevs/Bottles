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
- [FUNNY DOCTOR EMERGENCY](https://thelearnquesters.pages.dev/funny-doctor-emergency.html)
- [STICKMAN JAILBREAK STORY](https://studyplaying.github.io/stickman-jailbreak-story.html)
- [POKER QUEST](https://studyquests.github.io/poker-quest.html)
- [CATEGORY MERGE224](https://studyplayings.pages.dev/category-merge224.html)
- [BATTLEDUDES IO](https://studyplayings.web.app/battledudes-io.html)
- [HUNT AND SEEK](https://studyquests.github.io/hunt-and-seek.html)
- [MILITARY CUBES 2048](https://studyplayings.pages.dev/military-cubes-2048.html)
- [THE TRENDY MERMAID](https://studyplayings.web.app/the-trendy-mermaid.html)
- [ANIMATION COLORING ALPHABET LORE](https://quizverses.github.io/animation-coloring-alphabet-lore.html)
- [DOCTOR CHICKEN](https://studyquests.pages.dev/doctor-chicken.html)
- [HORROR FOREST BEAR](https://quizverses.pages.dev/horror-forest-bear.html)
- [MEGA RAMP CAR STUNTS](https://quizverses.github.io/mega-ramp-car-stunts.html)
- [WATERMELON MERGE](https://studyquests.github.io/watermelon-merge.html)
- [CHRISTMAS BLIND BOX](https://studyquests.github.io/christmas-blind-box.html)
- [MAGIC BUBBLES](https://studyplaying.github.io/magic-bubbles.html)
- [CATEGORY PARKOUR55](https://studyplayings.web.app/category-parkour55.html)
- [UGC MATH RACE](https://quizverses-9d2f2.web.app/ugc-math-race.html)
- [SPRING TILE MASTER](https://studyplayings.web.app/spring-tile-master.html)
- [NINJA DASH COZY TACTIC PUZZLE](https://quizverses.github.io/ninja-dash-cozy-tactic-puzzle.html)
- [SUPERMARKET MANAGER SIMULATOR](https://studyquests.github.io/supermarket-manager-simulator.html)
- [SUMMER TRIPLE MAHJONG](https://studyplaying.github.io/summer-triple-mahjong.html)
- [CATERFALL 2048](https://studyquests.github.io/caterfall-2048.html)
- [CATEGORY ESCAPE 2](https://studyplayings.pages.dev/category-escape-2.html)
- [INDEX14](https://quizverses.pages.dev/index14.html)
- [LABUBU AND ME](https://studyquests.pages.dev/labubu-and-me.html)
- [CATEGORY LOGIC538](https://quizverses-9d2f2.web.app/category-logic538.html)
- [CATEGORY BOOKMARKLETS](https://studyplayings.pages.dev/category-bookmarklets.html)
- [DIGWORM IO](https://quizverses.github.io/digworm-io.html)
- [MERMAIDCORE MAKEUP](https://quizverses.pages.dev/mermaidcore-makeup.html)
- [NUMBER DOMINATION](https://quizverses.github.io/number-domination.html)
- [SQUARE PUNKI LONG HAND](https://quizverses.github.io/square-punki-long-hand.html)
- [HAMMER MASTERCRAFT DESTROY](https://studyquests.github.io/hammer-mastercraft-destroy.html)
- [HANGMAN SAGA](https://studyplaying.github.io/hangman-saga.html)
- [CATEGORY SNAKE40](https://studyquests.pages.dev/category-snake40.html)
- [CONTACT](https://quizverses-9d2f2.web.app/contact.html)
- [IDLE DRIVE MERGE UPGRADE DRIVE](https://studyplayings.web.app/idle-drive-merge-upgrade-drive.html)
- [CANDY DOLL DRESS UP](https://studyquests.github.io/candy-doll-dress-up.html)
- [TROLLEY FUN](https://studyquests.github.io/trolley-fun.html)
- [ONLINE PORTAL](https://studyquests.github.io/)
- [STICKMAN GUN SHOOTER](https://studyplaying.github.io/stickman-gun-shooter.html)
- [CATEGORY CONTROLLER](https://studyplayings.pages.dev/category-controller.html)
- [HAWAII MATCH 5](https://studyquests.github.io/hawaii-match-5.html)
- [STREET TRAFFIC RACER](https://studyquests.github.io/street-traffic-racer.html)
- [FASHION CHALLENGE CATWALK RUN](https://quizverses.pages.dev/fashion-challenge-catwalk-run.html)
- [TOWER OF HELL OBBY BLOX](https://quizverses.pages.dev/tower-of-hell-obby-blox.html)
- [BUS COLOR JAM](https://studyquests.pages.dev/bus-color-jam.html)
- [HOW TO DRESS YOUR DRAGON](https://quizverses.pages.dev/how-to-dress-your-dragon.html)
- [REAL MOTORBIKE SUPER HERO STUNT 3D](https://studyplaying.github.io/real-motorbike-super-hero-stunt-3d.html)
- [MY LITTLE CAR WASH](https://quizverses.github.io/my-little-car-wash.html)
- [INDEX16](https://studyplayings.pages.dev/index16.html)
- [MISSILE LAUNCH MASTER](https://studyquests.pages.dev/missile-launch-master.html)
- [CATEGORY CRASH32](https://studyplayings.pages.dev/category-crash32.html)
- [SITEMAP](https://studyquests.github.io/sitemap.html)
- [CATEGORY CASUAL 5](https://quizverses-9d2f2.web.app/category-casual-5.html)
- [CATEGORY BYPASS](https://studyplayings.pages.dev/category-bypass.html)
- [BOBB S WORLD](https://studyquests.pages.dev/bobb-s-world.html)
- [TAP ARROW AWAY](https://quizverses.pages.dev/tap-arrow-away.html)
- [BLAST CUBES](https://quizverses.pages.dev/blast-cubes.html)
- [WATER SORT](https://quizverses.pages.dev/water-sort.html)
- [REACH 2048](https://quizverses.github.io/reach-2048.html)
- [BIG BAD APE](https://quizverses.pages.dev/big-bad-ape.html)
- [PLANT MERGE ZOMBIE WAR](https://studyquests.pages.dev/plant-merge-zombie-war.html)
- [CATEGORY CONTROLLER59](https://studyquests.pages.dev/category-controller59.html)
- [CUTE CRAFT LAB](https://studyquests.github.io/cute-craft-lab.html)
- [GT CHAMPIONSHIP ARCADE](https://studyquests.github.io/gt-championship-arcade.html)
- [CATEGORY CASUAL 2](https://studyplaying.github.io/category-casual-2.html)
- [STEAL ITEMS IO](https://studyplayings.pages.dev/steal-items-io.html)
- [CATEGORY ADVENTURE](https://quizverses-9d2f2.web.app/category-adventure.html)
- [CATEGORY CASUAL971](https://studyplaying.github.io/category-casual971.html)
- [CANDY MAKER DESSERT GAMES](https://studyplaying.github.io/candy-maker-dessert-games.html)
- [ZOMBIE FRONTIER SHOOTER](https://studyquesthub.web.app/zombie-frontier-shooter.html)
- [NINJA CROSSWORD CHALLENGE](https://studyplaying.github.io/ninja-crossword-challenge.html)
- [PIXEL SHOOT](https://studyplaying.github.io/pixel-shoot.html)
- [CATEGORY JIGSAW](https://studyplayings.pages.dev/category-jigsaw.html)
- [WOODS OF NEVIA FOREST SURVIVAL](https://studyquests.github.io/woods-of-nevia-forest-survival.html)
- [CAKE SORT](https://studyquests.github.io/cake-sort.html)
- [PARKING DRIVER](https://studyplaying.github.io/parking-driver.html)
- [ZOMBIE CHASE](https://quizverses.pages.dev/zombie-chase.html)
- [HIDDEN KITTY](https://studyquests.pages.dev/hidden-kitty.html)
- [JAVELIN BATTLE](https://quizverses.pages.dev/javelin-battle.html)
- [POPCATS MERGE THE CATS](https://quizverses.github.io/popcats-merge-the-cats.html)
- [BED WARS](https://quizverses.github.io/bed-wars.html)
- [COUNTRYSIDE DRIVING QUEST](https://studyquesthub.web.app/countryside-driving-quest.html)
- [NUBIK IN THE MONSTER WORLD](https://studyplayings.web.app/nubik-in-the-monster-world.html)
- [DRAW BRIDGE CHALLENGE](https://studyquests.pages.dev/draw-bridge-challenge.html)
- [CATEGORY COLLECT565](https://studyplayings.pages.dev/category-collect565.html)
- [HAPPY TOWN](https://studyquests.github.io/happy-town.html)
- [MATCH 3 DREAM ROOM](https://studyplayings.web.app/match-3-dream-room.html)
- [RIOT VILLAGE](https://studyplayings.pages.dev/riot-village.html)
- [BOUNCEPOP QUEST](https://studyplayings.pages.dev/bouncepop-quest.html)
- [MERMAIDCORE MAKEUP](https://quizverses.github.io/mermaidcore-makeup.html)
- [MATH CROSSWORD PUZZLE GENIUS EDITION](https://quizverses.github.io/math-crossword-puzzle-genius-edition.html)
- [MERGE THE COINS USSR](https://studyplaying.github.io/merge-the-coins-ussr.html)
- [BUSY BEE HIVE](https://studyplaying.github.io/busy-bee-hive.html)
- [KICK THE NOOBIK 3D](https://quizverses.pages.dev/kick-the-noobik-3d.html)
- [TERMS](https://studyquests.github.io/terms.html)
- [KNIFE MADNESS](https://studyplaying.github.io/knife-madness.html)
- [DARING JACK](https://studyplaying.github.io/daring-jack.html)
- [CATEGORY ADVENTURE 2](https://quizverses-9d2f2.web.app/category-adventure-2.html)
- [HORDE HUNTERS](https://studyplayings.web.app/horde-hunters.html)
- [BUILD A GO KART](https://quizverses.github.io/build-a-go-kart.html)
- [CHICKZ STACK](https://studyplaying.github.io/chickz-stack.html)
- [BLOCK CRAFT 3D](https://studyplayings.pages.dev/block-craft-3d.html)
- [CATEGORY ADVENTURE 3](https://quizverses-9d2f2.web.app/category-adventure-3.html)
- [RESCUE RIFT](https://quizverses.github.io/rescue-rift.html)
- [GOMU GOMAN](https://quizverses-9d2f2.web.app/gomu-goman.html)
- [PHONE CASE DIY 5](https://quizverses-9d2f2.web.app/phone-case-diy-5.html)
- [WAVE ROAD 3D](https://studyquests.github.io/wave-road-3d.html)
- [MOJICON EMOJI CONNECT](https://studyplaying.github.io/mojicon-emoji-connect.html)
- [WORDS WITH OWL](https://studyplayings.web.app/words-with-owl.html)
- [CATEGORY CAR](https://studyplayings.pages.dev/category-car.html)
- [FOREST TILES](https://studyplaying.github.io/forest-tiles.html)
- [DEAD BRAIN](https://studyquests.github.io/dead-brain.html)
- [BLOCK CRAFT 3D](https://quizverses-9d2f2.web.app/block-craft-3d.html)
- [FISH KINGDOM](https://studyplayings.pages.dev/fish-kingdom.html)
- [LITTLE LILY HALLOWEEN PREP](https://studyquests.github.io/little-lily-halloween-prep.html)
- [SPRUNKI 3D SHOOTER](https://studyquests.pages.dev/sprunki-3d-shooter.html)
- [CHALLENGER CITY DRIVER](https://studyplayings.web.app/challenger-city-driver.html)
- [ROPE COLOR SORT 3D](https://studyquests.pages.dev/rope-color-sort-3d.html)
- [ASSASSIN COMMANDO CAR DRIVING](https://quizverses.github.io/assassin-commando-car-driving.html)
- [TEACHER SIMULATOR](https://quizverses.pages.dev/teacher-simulator.html)
- [BELL MADNESS](https://studyplayings.web.app/bell-madness.html)
- [CATEGORY PROXY](https://studyplayings.pages.dev/category-proxy.html)
- [ELLIE AND FRIENDS ART BLOOM AESTHETIC](https://studyplayings.pages.dev/ellie-and-friends-art-bloom-aesthetic.html)
- [ESCAPE THE HORROR CRAFT](https://studyplaying.github.io/escape-the-horror-craft.html)
- [ONLINE PORTAL](https://studyplayings.pages.dev/)
- [INDEX4](https://studyquests.github.io/index4.html)
- [BUBBLE SHOOTER WITCH TOWER 2](https://quizverses-9d2f2.web.app/bubble-shooter-witch-tower-2.html)
- [EAT DONUTS](https://studyplaying.github.io/eat-donuts.html)
- [THE ZOMBIE HOUSE](https://studyplayings.web.app/the-zombie-house.html)
