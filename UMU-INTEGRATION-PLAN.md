# UMU Integration Plan for Bottles

## Product shape

UMU does not get a button in the main title bar and it does not become a third main view. It is integrated into the two places that already own these concepts.

The Bottles view shows a separate UMU Prefixes group next to normal Bottles and Steam Proton prefixes. Each row exposes the prefix path, Proton selection and only the states that require action. The full row opens its settings while the folder button opens the prefix.

The existing Library shows UMU games together with the other programs. UMU entries carry a visible badge on the cover and open a dedicated per-game settings dialog. They remain separate from Bottle programs internally, so they do not need a fake Bottle configuration.

The add button keeps its normal Create Bottle behavior in the Bottles view. In the Library it opens a search backed by the official UMU database. A persistent Library card also links to this setup and to the existing Add to Library action inside a Bottle.

Global UMU configuration lives in a dedicated UMU page inside Bottles Preferences.

## Launcher selection and packaging

Native packages prefer an existing `umu-run` from the system. The Flatpak contains a pinned official UMU launcher and uses it when no different launcher is configured. This avoids asking Flatpak users to install a host tool the sandbox may not be able to see.

The provider validates the selected executable with `umu-run --version` before exposing it to the interface. The Preferences page reports its path, version and source as System, Bundled, Custom or Managed.

The Flatpak grants access to `xdg-data/umu`, where the official launcher keeps its runtime data, and `~/Games/umu`, where UMU creates standard prefixes. The bundled launcher and its license are installed as separate build modules.

## Data ownership

Each UMU game has a small Bottles-owned definition containing:

- Name, executable and working directory
- Proton selection
- UMU `GAMEID` and `STORE`
- Prefix path and ownership flag
- Launch arguments and environment variables
- Dependency installer choice and installed dependency metadata
- Setup state

Managed prefixes live below the Bottles UMU data directory. Prefixes detected in `~/Games/umu` remain external and appear automatically as entries that need setup. Manually registered prefixes keep their original absolute path and are also marked external. Bottles can delete a managed prefix only after checking that it belongs to the selected game. External prefixes are never deleted by Bottles.

Writes use temporary files and atomic replacement. Unknown fields are preserved so a future schema can extend a game definition without losing data when an older field is edited.

## New game flow

Add Windows Game first searches the official UMU database by title, store, codename, acronym or UMU ID. Selecting a result fills its title, `GAMEID` and store, then asks whether to run an installer or use an existing executable. The database supplies identity and Protonfixes metadata only. It does not download games. The custom path remains available for games not listed in the database.

Database results are fetched from `https://umu.openwinecomponents.org/umu_api.php`, cached for 24 hours and searched locally. A stale cache remains usable while offline. The dialog links to the source at `https://github.com/Open-Wine-Components/umu-database` and identifies its GPL-3.0 license.

For an installer, Bottles creates the managed prefix definition, adds the entry to the Library and runs the selected file through UMU. For an existing executable, Bottles saves the game immediately with the selected prefix.

When installation ends, the game remains in the Library and Bottles asks the user to select the installed executable in its settings. The same dialog can later change its launch arguments, working directory, environment, Proton version and identity.

Prefixes found in `~/Games/umu` appear automatically in the Bottles view. Selecting one starts with the same database search, then asks for the installed executable and completes its game metadata without taking ownership of the directory. The custom setup can select a non-standard prefix manually.

## What UMU receives at launch

Bottles runs `umu-run` directly, without a shell, and builds the protected UMU environment itself:

```text
WINEPREFIX=<selected prefix>
GAMEID=<protonfixes game id or umu-default>
STORE=<official UMU store identifier>
PROTONPATH=<selected Proton build>
STEAM_COMPAT_INSTALL_PATH=<game directory>
```

User environment variables are added separately. Reserved UMU variables cannot be overridden in the custom environment field.

## Protonfixes, Bottles Dependencies and Winetricks

These solve different parts of the setup and must not be presented as the same tool.

Protonfixes stays under UMU control. `GAMEID` and `STORE` let UMU identify a known game and apply the matching Proton fix automatically. The store identifier for Epic is `egs`, which is the value expected by the UMU database.

Bottles Dependencies is the default manual component source. Bottles reads its own dependency recipes and accepts only actions that are safe and meaningful for an UMU prefix. The first implementation supports downloaded installers and DLL overrides. A recipe that also needs registry actions, Windows-version changes, font operations or another unsupported Bottles action is rejected before anything is downloaded or changed. This keeps the result predictable instead of pretending every existing recipe already maps to UMU.

Winetricks is the alternative manual component source. Bottles sends validated verb names through `umu-run winetricks`, which keeps the operation inside the same Proton and prefix environment. Arguments are passed as an argument vector and never through shell expansion.

The default tool is selected in Preferences. Each game stores its own choice, so changing the global default affects new games without silently changing existing ones. The per-game dialog lets the user switch installer and enter component names before installation.

Examples:

```text
Bottles Dependencies: vcredist2022
Winetricks: vcrun2022 corefonts
```

The names are not translated between catalogs. Bottles dependency names are looked up in the Bottles dependency repository. Winetricks names remain Winetricks verbs.

## Library behavior and process lifecycle

Launching an UMU entry swaps the Library action to Stop. Bottles tracks the whole process group rather than only the first `umu-run` process, because the launcher may exit before the Windows child processes.

Before starting, changing launchers or deleting metadata, Bottles checks whether the prefix is already in use. This also protects games that survived an application restart and are no longer present in the in-memory process table.

Installer and dependency jobs run outside the GTK thread. Controls that could save, remove or start a second operation are disabled until the current operation finishes.

## Local verification before review

The local build must prove all of the following before the work is proposed upstream:

- The Flatpak contains the expected official `umu-run` and license
- The UMU Preferences page reads the real launcher status
- A managed game and an external prefix survive an application restart
- A standard prefix appears automatically and opens the setup flow
- A database result fills the correct `GAMEID` and store
- The cached database remains searchable without a connection
- Both appear in the Bottles view and the Library
- Per-game settings persist, including the dependency installer choice
- A harmless Windows executable starts and stops through UMU
- A running prefix cannot be launched twice or deleted
- The Bottles dependency path rejects an unsupported recipe before mutation
- The Winetricks path uses validated verbs and the selected prefix
