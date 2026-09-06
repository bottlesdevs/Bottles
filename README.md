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
- [OBBY PINATA PARTY](https://studyquests.pages.dev/obby-pinata-party.html)
- [TWO CARTS DOWNHILL](https://thequizzone.pages.dev/two-carts-downhill.html)
- [MAHJONG AT HOME SCANDINAVIAN EDITION](https://iskillplay.web.app/mahjong-at-home-scandinavian-edition.html)
- [CELEBRITIES GET READY FOR CHRISTMAS](https://themindplaying.web.app/celebrities-get-ready-for-christmas.html)
- [STICK NINJA SURVIVAL](https://thequizzone.pages.dev/stick-ninja-survival.html)
- [CATEGORY POOL 2](https://themindskillplayplay.pages.dev/category-pool-2.html)
- [HAPPY JUMP](https://thequizzone.pages.dev/happy-jump.html)
- [DROP KICK WORLD CUP 2018](https://themindplays.pages.dev/drop-kick-world-cup-2018.html)
- [ASMR WASHING FIXING](https://iskillplay.web.app/asmr-washing-fixing.html)
- [FUN TOWN PARKING](https://theskillquest.pages.dev/fun-town-parking.html)
- [ARENA](https://themindplay.github.io/arena.html)
- [FARM VS ZOMBIES](https://iskillquest.pages.dev/farm-vs-zombies.html)
- [AIDAN IN DANGER](https://skillplay.github.io/aidan-in-danger.html)
- [WORM OUT BRAIN TEASER GAMES](https://themindplay.pages.dev/worm-out-brain-teaser-games.html)
- [CLOCKWORK](https://themindplay.pages.dev/clockwork.html)
- [GIANT WANTED MONSTER](https://theskillquest.pages.dev/giant-wanted-monster.html)
- [STARRY STYLE DORAMA OF DREAM](https://thequizzone.pages.dev/starry-style-dorama-of-dream.html)
- [UNDERWATER SURVIVAL](https://iskillquest.pages.dev/underwater-survival.html)
- [CAPYBARA MUKBANG ASMR](https://themindskillplayplay.pages.dev/capybara-mukbang-asmr.html)
- [COSMOS 404](https://themindplays.pages.dev/cosmos-404.html)
- [SAVE MY HERO](https://iskillquest.pages.dev/save-my-hero.html)
- [DREAM RESTAURANT 3D](https://iskillquest.pages.dev/dream-restaurant-3d.html)
- [BUILD AN AQUAPARK](https://thequizzone.pages.dev/build-an-aquapark.html)
- [FLOWER BLOCK](https://themindplays.pages.dev/flower-block.html)
- [CAR RACING 3D DRIVE MAD](https://skillplay.github.io/car-racing-3d-drive-mad.html)
- [SPECIAL HOLIDAY SOLITAIRE](https://themindzone.pages.dev/special-holiday-solitaire.html)
- [GUINEA PIGGY MATCHING](https://iskillquest.pages.dev/guinea-piggy-matching.html)
- [GLOVES GROW RUSH](https://skillplay.github.io/gloves-grow-rush.html)
- [CATEGORY SOCCER 2](https://iskillplay.web.app/category-soccer-2.html)
- [CATEGORY HERO71](https://iskillplay.web.app/category-hero71.html)
- [BUCKSHOT ROULETTE](https://theskillquest.pages.dev/buckshot-roulette.html)
- [AVENGER GUARD](https://theskillquest.pages.dev/avenger-guard.html)
- [CATEGORY IDLE CLICKER GAME](https://iskillplay.web.app/category-idle-clicker-game.html)
- [CATEGORY GUN241](https://iskillplay.web.app/category-gun241.html)
- [CATEGORY RACING DRIVING 2](https://themindplays.pages.dev/category-racing-driving-2.html)
- [WORLDCRAFT 3](https://skillplay.github.io/worldcraft-3.html)
- [CATEGORY DRAWING](https://themindzone.pages.dev/category-drawing.html)
- [BOTTLE CHALLENGE](https://thequizzone.pages.dev/bottle-challenge.html)
- [MONSTER SLAYER MERGE SURVIVE](https://themindplaying.web.app/monster-slayer-merge-survive.html)
- [VALLEY OF WOLVES AMBUSH](https://iskillquest.pages.dev/valley-of-wolves-ambush.html)
- [INDEX42](https://themindzone.pages.dev/index42.html)
- [CATEGORY DESTROY](https://themindskillplayplay.pages.dev/category-destroy.html)
- [NUBIK CREATE YOUR PLACE](https://iskillquest.pages.dev/nubik-create-your-place.html)
- [BRICK GAME CLASSIC](https://iskillquest.pages.dev/brick-game-classic.html)
- [PRINCESS VALENTINES CRUSH](https://skillplay.github.io/princess-valentines-crush.html)
- [BLUE MUSHROOM CAT RUN](https://theskillquest.pages.dev/blue-mushroom-cat-run.html)
- [FLOWBALL](https://theskillquest.pages.dev/flowball.html)
- [TURBO STUNT RACING](https://themindskillplayplay.pages.dev/turbo-stunt-racing.html)
- [INDEX27](https://themindzone.pages.dev/index27.html)
- [MR DUDE KING OF THE HILL](https://theskillquest.pages.dev/mr-dude-king-of-the-hill.html)
- [FOAM AND FIND](https://skillplay.github.io/foam-and-find.html)
- [MANSION STORY MATCH](https://iskillquest.pages.dev/mansion-story-match.html)
- [PLANE CRASH RAGDOLL SIMULATOR](https://skillplay.github.io/plane-crash-ragdoll-simulator.html)
- [CHICKEN BLAST](https://iskillquest.pages.dev/chicken-blast.html)
- [CATEGORY CASUAL 6](https://themindplays.pages.dev/category-casual-6.html)
- [KITTY SCRAMBLE](https://themindplaying.web.app/kitty-scramble.html)
- [CATEGORY INTERSTELLARUNBLOCKER](https://iskillplay.web.app/category-interstellarunblocker.html)
- [CATEGORY HORROR90](https://themindzone.pages.dev/category-horror90.html)
- [OUTSIDE](https://iskillquest.pages.dev/outside.html)
- [BOOM STICK BAZOOKA](https://thequizzone.pages.dev/boom-stick-bazooka.html)
- [CATEGORY MERGE](https://themindzone.pages.dev/category-merge.html)
- [BOMB EVOLUTION](https://themindskillplayplay.pages.dev/bomb-evolution.html)
- [HORROR MINECRAFT PARTYTIME](https://thequizzone.pages.dev/horror-minecraft-partytime.html)
- [EVERMATCH](https://theskillquest.pages.dev/evermatch.html)
- [FIND SORT MATCH](https://themindskillplayplay.pages.dev/find-sort-match.html)
- [CATEGORY AGILITY 3](https://themindzone.pages.dev/category-agility-3.html)
- [CATEGORY BUILDING182](https://themindplaying.web.app/category-building182.html)
- [CODE RUNNER BINARY CONFUSION](https://themindplay.pages.dev/code-runner-binary-confusion.html)
- [CATEGORY DOG18](https://themindplays.pages.dev/category-dog18.html)
- [MATCH ARENA](https://themindplaying.web.app/match-arena.html)
- [CATEGORY MOBILE2 095](https://iskillplay.web.app/category-mobile2-095.html)
- [FAT CAT LIFE](https://themindskillplayplay.pages.dev/fat-cat-life.html)
- [CATEGORY CAR 2](https://themindskillplayplay.pages.dev/category-car-2.html)
- [CANNON SHOOTER](https://iskillquest.pages.dev/cannon-shooter.html)
- [CATEGORY CASUAL969](https://themindplays.pages.dev/category-casual969.html)
- [CATEGORY BOOKMARKLETS](https://themindplays.pages.dev/category-bookmarklets.html)
- [CATEGORY ANIMAL215](https://iskillquest.pages.dev/category-animal215.html)
- [TERMS](https://themindzone.pages.dev/terms.html)
- [CATEGORY HORROR 3](https://iskillplay.web.app/category-horror-3.html)
- [PET DOCTOR BUSINESS TYCOON PET CARE GAME](https://themindskillplayplay.pages.dev/pet-doctor-business-tycoon-pet-care-game.html)
- [PIECE OF CAKE MERGE AND BAKE](https://skillplay.github.io/piece-of-cake-merge-and-bake.html)
- [MINE FPS SHOOTER NOOB ARENA](https://thequizzone.pages.dev/mine-fps-shooter-noob-arena.html)
- [VALENTINES LOVE LINK](https://iskillquest.pages.dev/valentines-love-link.html)
- [CATEGORY DRESS UP](https://themindplays.pages.dev/category-dress-up.html)
- [COIN EMPIRE](https://thequizzone.pages.dev/coin-empire.html)
- [LAST WAR SURVIVAL](https://iskillquest.pages.dev/last-war-survival.html)
- [CATEGORY ADVENTURE](https://themindplaying.web.app/category-adventure.html)
- [KINGS AND QUEENS MATCH 2](https://thequizzone.pages.dev/kings-and-queens-match-2.html)
- [ARMY TRUCK DRIVER ONLINE](https://thequizzone.pages.dev/army-truck-driver-online.html)
- [OFFROAD JEEP GAME SIMULATOR](https://thequizzone.pages.dev/offroad-jeep-game-simulator.html)
- [MERGE HERO SURVIVAL TOWER DEFENSE](https://thequizzone.pages.dev/merge-hero-survival-tower-defense.html)
- [INDEX16](https://iskillquest.pages.dev/index16.html)
- [NAUTILUS SPACESHIP ESCAPE](https://themindskillplayplay.pages.dev/nautilus-spaceship-escape.html)
- [LUNAR PHASE BATTLE](https://theskillquest.pages.dev/lunar-phase-battle.html)
- [CATEGORY 204828](https://themindzone.pages.dev/category-204828.html)
- [CATEGORY INTERSTELLARNETWORK](https://iskillplay.web.app/category-interstellarnetwork.html)
- [CATEGORY PIXEL313](https://iskillplay.web.app/category-pixel313.html)
- [DR PARKING](https://iskillquest.pages.dev/dr-parking.html)
- [CATEGORY BLOODY29](https://themindplays.pages.dev/category-bloody29.html)
- [STICKMAN PRISON AND LOVE](https://thequizzone.pages.dev/stickman-prison-and-love.html)
- [CATEGORY AGILITY](https://themindzone.pages.dev/category-agility.html)
- [PANDA MAHJONG CLASSIC](https://themindzone.pages.dev/panda-mahjong-classic.html)
- [CATEGORY ARCHERY52](https://themindzone.pages.dev/category-archery52.html)
- [ERASE THE EXTRA ELEMENT](https://theskillquest.pages.dev/erase-the-extra-element.html)
- [KILLER ESCAPE HUGGY EXTREME](https://thequizzone.pages.dev/killer-escape-huggy-extreme.html)
- [CATEGORY PUZZLE 8](https://iskillplay.web.app/category-puzzle-8.html)
- [1010 ELIXIR ALCHEMY](https://iskillquest.pages.dev/1010-elixir-alchemy.html)
- [DICE PUZZLE](https://themindskillplayplay.pages.dev/dice-puzzle.html)
- [CATEGORY BUBBLE SHOOTER](https://themindplays.pages.dev/category-bubble-shooter.html)
- [POTION MERGE WITCH](https://thequizzone.pages.dev/potion-merge-witch.html)
- [CATEGORY BRAIN261](https://themindplays.pages.dev/category-brain261.html)
- [CATEGORY CASUAL 15](https://themindplays.pages.dev/category-casual-15.html)
- [PARTY GAMES MINI SHOOTER BATTLE](https://iskillquest.pages.dev/party-games-mini-shooter-battle.html)
- [CATEGORY MAHJONG CONNECT 2](https://iskillquest.pages.dev/category-mahjong-connect-2.html)
- [DROP ANIMALS](https://themindplay.pages.dev/drop-animals.html)
- [CAKE MERGE 2](https://themindskillplayplay.pages.dev/cake-merge-2.html)
- [DYNAMONS 7](https://themindzone.pages.dev/dynamons-7.html)
- [CATEGORY BASKETBALL 3](https://iskillquest.pages.dev/category-basketball-3.html)
- [CATEGORY MAKEUP51](https://themindzone.pages.dev/category-makeup51.html)
- [PIGGY CLICKER](https://skillplay.github.io/piggy-clicker.html)
- [HOME RUSH THE FISH WAR](https://theskillquest.pages.dev/home-rush-the-fish-war.html)
- [INDEX22](https://themindzone.pages.dev/index22.html)
- [CATEGORY PLATFORM260](https://iskillplay.web.app/category-platform260.html)
- [CATEGORY BIKE](https://themindplays.pages.dev/category-bike.html)
- [DIG OUT OF PRISON](https://skillplay.github.io/dig-out-of-prison.html)
- [ZEN MASTER 3 TILES](https://theskillquest.pages.dev/zen-master-3-tiles.html)
- [CATEGORY ADVENTURE 3](https://themindskillplayplay.pages.dev/category-adventure-3.html)
- [CRAB GUARDS](https://themindplay.pages.dev/crab-guards.html)
- [STICKMAN TEAM DETROIT](https://themindskillplayplay.pages.dev/stickman-team-detroit.html)
- [WORDS WITH OWL](https://skillplay.github.io/words-with-owl.html)
