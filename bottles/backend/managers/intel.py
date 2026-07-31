# intel.py
#
# Copyright 2026 mirkobrombin <brombin94@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, in version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import os
import re
import sqlite3
from difflib import SequenceMatcher
from gettext import gettext as _
from pathlib import Path
from typing import ClassVar

from bottles.backend.globals import Paths
from bottles.backend.logger import Logger

logging = Logger()

SCHEMA_VERSION = "1"
PACKAGED_DB_PATH = str(Path(__file__).resolve().parents[3] / "eagle-intel.sqlite")
REQUIRED_TABLES = {"artifact", "meta", "report_agg", "software", "trick", "tweak"}

ENV_ALLOWED_PREFIXES = ("DXVK_", "VKD3D_", "WINE_")
ENV_ALLOWED_EXACT = {"PULSE_LATENCY_MSEC", "STAGING_SHARED_MEMORY"}
ENV_DENIED_EXACT = {"WINEARCH", "WINEPREFIX"}
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
ENV_VALUE_RE = re.compile(r"^[A-Za-z0-9_.,:+/@% -]*$")
DLL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
ARG_RE = re.compile(r"^--?[A-Za-z0-9][A-Za-z0-9._:+/@,-]*(?:=[A-Za-z0-9._:+/@,-]+)?$")

GENERIC_NAMES = {
    "application",
    "client",
    "game",
    "install",
    "installer",
    "launcher",
    "setup",
    "start",
    "update",
    "updater",
}

LAUNCH_FLAG_MAP = {
    "enableNvapi": ("dxvk_nvapi", True, _("community enables NVAPI")),
    "useWineD9vk": ("dxvk", True, _("community uses D9VK/DXVK for d3d9")),
    "useWineD3d11": ("dxvk", False, _("community falls back to WineD3D")),
    "disableEsync": ("sync", "wine", _("community disables esync")),
    "disableFsync": ("sync", "wine", _("community disables fsync")),
}

PROTON_ENV_MAP = {
    "PROTON_ENABLE_NVAPI": ("dxvk_nvapi", True, _("community enables NVAPI")),
    "PROTON_USE_WINED3D": ("dxvk", False, _("community falls back to WineD3D")),
    "PROTON_NO_ESYNC": ("sync", "wine", _("community disables esync")),
    "PROTON_NO_FSYNC": ("sync", "wine", _("community disables fsync")),
}

SOURCE_ATTRIBUTION = {
    "protondb": {
        "name": "ProtonDB",
        "dataset": "protondb-data",
        "url": "https://github.com/bdefore/protondb-data",
        "licenses": [
            {
                "name": "ODbL 1.0",
                "url": "https://opendatacommons.org/licenses/odbl/1-0/",
            },
            {
                "name": "DbCL 1.0",
                "url": "https://opendatacommons.org/licenses/dbcl/1-0/",
            },
        ],
    },
    "winetricks": {
        "name": "winetricks",
        "dataset": _("application verb metadata"),
        "url": "https://github.com/Winetricks/winetricks",
        "licenses": [
            {
                "name": "LGPL-2.1-or-later",
                "url": (
                    "https://github.com/Winetricks/winetricks/blob/master/COPYING"
                ),
            }
        ],
    },
    "bottles_dependencies": {
        "name": "Bottles dependencies",
        "dataset": _("dependency name mapping"),
        "url": "https://github.com/bottlesdevs/dependencies",
        "licenses": [],
    },
}


class EagleIntel:
    """Read-only client for the Eagle compatibility intelligence database."""

    _OVERRIDE_MODES: ClassVar[dict[str, str]] = {
        "native": "n",
        "builtin": "b",
        "native,builtin": "n,b",
        "builtin,native": "b,n",
        "disabled": "d",
    }

    def __init__(self, db_path: str | None = None):
        user_db_path = os.path.join(Paths.base, "eagle_intel.sqlite")
        requested_path = db_path or os.environ.get("EAGLE_INTEL_DB")
        if requested_path:
            candidates = [requested_path]
        else:
            candidates = [user_db_path, PACKAGED_DB_PATH]

        self.db_path = candidates[0]
        self._conn = None
        self._has_artifacts = False
        for candidate in dict.fromkeys(candidates):
            self.db_path = candidate
            self.__open()
            if self.available:
                break

    def __open(self) -> None:
        if not os.path.isfile(self.db_path):
            return

        try:
            uri = f"{Path(self.db_path).resolve().as_uri()}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row

            tables = {
                row["name"]
                for row in self._conn.execute(
                    "SELECT name FROM sqlite_schema WHERE type = 'table'"
                ).fetchall()
            }
            missing_tables = REQUIRED_TABLES - tables
            if missing_tables:
                missing = ", ".join(sorted(missing_tables))
                logging.warning(f"[EagleIntel] Database is missing tables: {missing}")
                self.close()
                return

            version = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?", ("schema_version",)
            ).fetchone()
            if version is None or version["value"] != SCHEMA_VERSION:
                found = version["value"] if version else "unknown"
                logging.warning(f"[EagleIntel] Unsupported database schema {found}")
                self.close()
                return

            self._has_artifacts = bool(
                self._conn.execute("SELECT EXISTS(SELECT 1 FROM artifact)").fetchone()[
                    0
                ]
            )
        except (OSError, sqlite3.Error) as e:
            logging.warning(f"[EagleIntel] Cannot open {self.db_path}: {e}")
            self.close()

    @property
    def available(self) -> bool:
        return self._conn is not None

    @property
    def has_artifacts(self) -> bool:
        return self._has_artifacts

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._has_artifacts = False

    @staticmethod
    def find_steam_appid(exe_path: str) -> str:
        """Discover the Steam AppID for an executable, if any."""
        exe_dir = os.path.dirname(os.path.abspath(exe_path))

        for directory in (exe_dir, os.path.dirname(exe_dir)):
            try:
                with open(os.path.join(directory, "steam_appid.txt")) as file:
                    appid = file.read().strip().split()[0]
                    if appid.isdigit():
                        return appid
            except (OSError, IndexError):
                pass

        parts = exe_dir.split(os.sep)
        if "common" not in parts:
            return ""

        index = next(
            (
                position
                for position, part in enumerate(parts)
                if part == "common"
                and position >= 1
                and parts[position - 1] == "steamapps"
                and len(parts) > position + 1
            ),
            -1,
        )
        if index < 0:
            return ""

        steamapps = os.sep.join(parts[:index])
        installdir = parts[index + 1]
        try:
            for entry in os.listdir(steamapps):
                if not entry.startswith("appmanifest_"):
                    continue
                with open(os.path.join(steamapps, entry), errors="ignore") as manifest:
                    contents = manifest.read()
                match = re.search(r'"installdir"\s+"([^"]+)"', contents)
                if not match or match.group(1).casefold() != installdir.casefold():
                    continue
                match = re.search(r'"appid"\s+"(\d+)"', contents)
                if match:
                    return match.group(1)
        except OSError:
            pass
        return ""

    @staticmethod
    def __normalize_name(value: str) -> str:
        normalized = re.sub(
            r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])",
            " ",
            value.casefold(),
        )
        return re.sub(r"[^a-z0-9]+", " ", normalized).strip()

    def __fuzzy_lookup(self, name: str):
        normalized = self.__normalize_name(name)
        if len(normalized) < 6 or normalized in GENERIC_NAMES:
            return None

        rows = self._conn.execute(
            "SELECT s.id, s.name, COALESCE(a.reports, 0) AS reports "
            "FROM software s "
            "LEFT JOIN report_agg a ON a.software_id = s.id "
            "WHERE s.source != 'protondb' OR a.reports >= 10 "
            "ORDER BY COALESCE(a.reports, 0) DESC"
        ).fetchall()

        best = None
        best_score = 0.0
        numbers = re.findall(r"\d+", normalized)
        for row in rows:
            candidate = self.__normalize_name(row["name"])
            if not candidate:
                continue
            if re.findall(r"\d+", candidate) != numbers:
                continue
            coverage = min(len(normalized), len(candidate)) / max(
                len(normalized), len(candidate)
            )
            score = SequenceMatcher(None, normalized, candidate).ratio()
            if coverage >= 0.65 and score >= 0.8 and score > best_score:
                best = row
                best_score = score
        return best

    def lookup(
        self,
        sha256: str = "",
        imphash: str = "",
        steam_appid: str = "",
        product_name: str = "",
        names: list | None = None,
    ) -> dict | None:
        """Resolve software by artifact, Steam AppID, exact name, then fuzzy name."""
        if not self.available:
            return None

        try:
            return self.__lookup(
                sha256=sha256,
                imphash=imphash,
                steam_appid=steam_appid,
                product_name=product_name,
                names=names,
            )
        except sqlite3.Error as e:
            logging.warning(f"[EagleIntel] Lookup failed: {e}")
            return None

    def __lookup(
        self,
        sha256: str,
        imphash: str,
        steam_appid: str,
        product_name: str,
        names: list,
    ) -> dict | None:
        def by_artifact(field: str, value: str):
            if not value:
                return None
            queries = {
                "sha256": (
                    "SELECT software_id AS id FROM artifact "
                    "WHERE sha256 = ? AND software_id IS NOT NULL LIMIT 1"
                ),
                "imphash": (
                    "SELECT software_id AS id FROM artifact "
                    "WHERE imphash = ? AND software_id IS NOT NULL LIMIT 1"
                ),
            }
            return self._conn.execute(queries[field], (value,)).fetchone()

        software_id = None
        match_level = None
        if self.has_artifacts:
            for level, row in (
                ("sha256", by_artifact("sha256", sha256)),
                ("imphash", by_artifact("imphash", imphash)),
            ):
                if row:
                    software_id, match_level = row["id"], level
                    break

        if software_id is None and steam_appid:
            row = self._conn.execute(
                "SELECT id FROM software WHERE steam_appid = ?", (steam_appid,)
            ).fetchone()
            if row:
                software_id, match_level = row["id"], "steam_appid"

        candidates = []
        for candidate in [product_name] + list(names or []):
            if (
                candidate
                and candidate not in candidates
                and candidate.casefold() != "unknown"
            ):
                candidates.append(candidate)

        if software_id is None:
            for name in candidates:
                normalized = self.__normalize_name(name)
                if len(normalized) < 4 or normalized in GENERIC_NAMES:
                    continue
                row = self._conn.execute(
                    "SELECT s.id FROM software s "
                    "LEFT JOIN report_agg a ON a.software_id = s.id "
                    "WHERE s.name = ? COLLATE NOCASE "
                    "ORDER BY COALESCE(a.reports, 0) DESC LIMIT 1",
                    (name,),
                ).fetchone()
                if row:
                    software_id, match_level = row["id"], "name"
                    break

        if software_id is None:
            for name in candidates:
                row = self.__fuzzy_lookup(name)
                if row:
                    software_id, match_level = row["id"], "fuzzy"
                    break

        if software_id is None:
            return None

        software = self._conn.execute(
            "SELECT s.name, s.steam_appid, s.trick_name, s.source, "
            "COALESCE(a.reports, 0) AS reports, "
            "COALESCE(a.verdict_yes, 0) AS verdict_yes, "
            "COALESCE(a.verdict_no, 0) AS verdict_no, "
            "COALESCE(a.tinkered, 0) AS tinkered, a.tier "
            "FROM software s "
            "LEFT JOIN report_agg a ON a.software_id = s.id "
            "WHERE s.id = ?",
            (software_id,),
        ).fetchone()
        if software is None:
            return None

        tweaks = self._conn.execute(
            "SELECT kind, value, evidence FROM tweak WHERE software_id = ? "
            "ORDER BY evidence DESC",
            (software_id,),
        ).fetchall()

        return {
            "match": match_level,
            "software": dict(software),
            "tweaks": [dict(tweak) for tweak in tweaks],
        }

    def trick(self, name: str) -> dict | None:
        if not self.available:
            return None
        try:
            row = self._conn.execute(
                "SELECT name, kind, title, files_json, overrides_json, winver, "
                "bottles_dep FROM trick WHERE name = ?",
                (name,),
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logging.warning(f"[EagleIntel] Trick lookup failed: {e}")
            return None

    @staticmethod
    def __json_list(value: str) -> list:
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def __attributions(*sources: str) -> list[dict]:
        return [
            {
                **SOURCE_ATTRIBUTION[source],
                "licenses": [
                    license_info.copy()
                    for license_info in SOURCE_ATTRIBUTION[source]["licenses"]
                ],
            }
            for source in sources
        ]

    def __plan_from_trick(self, hit: dict) -> dict:
        software = hit["software"]
        trick = self.trick(software.get("trick_name") or "") or {}

        dll_overrides = {}
        for override in self.__json_list(trick.get("overrides_json")):
            mode = self._OVERRIDE_MODES.get(override.get("mode", ""))
            if mode is None:
                continue
            for dll in override.get("dlls", []):
                if DLL_NAME_RE.fullmatch(dll):
                    dll_overrides.setdefault(
                        dll.lower(), {"value": mode, "evidence": 0}
                    )

        dependencies = []
        if trick.get("bottles_dep"):
            dependencies.append(
                {
                    "name": trick["bottles_dep"],
                    "evidence": 0,
                    "reason": _(
                        "winetricks {verb} maps to this dependency"
                    ).format(verb=trick["name"]),
                }
            )

        notes = [
            _("Known application: {name} (winetricks verb '{verb}')").format(
                name=software["name"], verb=software.get("trick_name")
            )
        ]
        if trick.get("winver"):
            notes.append(
                _("winetricks sets Windows version to {version} for it").format(
                    version=trick["winver"]
                )
            )

        return {
            "match": hit["match"],
            "source": "winetricks",
            "attributions": self.__attributions(
                "winetricks",
                *(("bottles_dependencies",) if dependencies else ()),
            ),
            "name": software["name"],
            "steam_appid": None,
            "tier": None,
            "reports": 0,
            "verdict_yes": 0,
            "verdict_no": 0,
            "parameters": {},
            "env": {},
            "dll_overrides": dll_overrides,
            "args": [],
            "dependencies": dependencies,
            "notes": notes,
        }

    def plan(self, hit: dict) -> dict:
        """Translate recurring community evidence into configuration hints."""
        software = hit["software"]
        if software.get("source") == "winetricks":
            return self.__plan_from_trick(hit)

        reports = max(software["reports"], 1)
        threshold = max(3, int(reports * 0.02))

        parameters = {}
        env = {}
        dll_overrides = {}
        args = []
        dependencies = []
        notes = []
        attribution_sources = ["protondb"]

        def propose_parameter(key, value, evidence, reason):
            current = parameters.get(key)
            if current is None or evidence > current["evidence"]:
                parameters[key] = {
                    "value": value,
                    "evidence": evidence,
                    "reason": reason,
                }

        for tweak in hit["tweaks"]:
            kind = tweak["kind"]
            value = tweak["value"]
            evidence = tweak["evidence"]
            if evidence < threshold:
                continue

            if kind == "launch_flag" and value in LAUNCH_FLAG_MAP:
                key, target, reason = LAUNCH_FLAG_MAP[value]
                propose_parameter(key, target, evidence, reason)
                continue

            if kind == "launch_token" and "=" in value:
                name, _separator, target = value.partition("=")
                target = target.strip("\"'")
                if name in PROTON_ENV_MAP and target.casefold() in ("1", "true"):
                    key, parameter_value, reason = PROTON_ENV_MAP[name]
                    propose_parameter(key, parameter_value, evidence, reason)
                    continue

                if name == "WINEDLLOVERRIDES":
                    specification = target.replace("\\", "")
                    for pair in specification.split(";"):
                        dlls, separator, mode = pair.partition("=")
                        if not separator:
                            continue
                        mode = self._OVERRIDE_MODES.get(mode, mode)
                        if mode not in {"n", "b", "n,b", "b,n", "d"}:
                            continue
                        for dll in dlls.split(","):
                            dll = dll.strip("\"'").lower()
                            if DLL_NAME_RE.fullmatch(dll) and dll not in dll_overrides:
                                dll_overrides[dll] = {
                                    "value": mode,
                                    "evidence": evidence,
                                }
                    continue

                if (
                    ENV_NAME_RE.fullmatch(name)
                    and name not in ENV_DENIED_EXACT
                    and (
                        name in ENV_ALLOWED_EXACT
                        or name.startswith(ENV_ALLOWED_PREFIXES)
                    )
                    and len(target) <= 64
                    and ENV_VALUE_RE.fullmatch(target)
                ):
                    env.setdefault(name, {"value": target, "evidence": evidence})
                continue

            if kind == "launch_token":
                if len(args) < 3 and ARG_RE.fullmatch(value):
                    args.append({"value": value, "evidence": evidence})
                continue

            if kind == "customization" and value == "mediaFoundation":
                notes.append(
                    _(
                        "Community reports needing a Media Foundation workaround "
                        "(x{evidence})"
                    ).format(evidence=evidence)
                )
                continue

            if kind == "custom_proton" and value.startswith("GE-Proton"):
                ge_proton_note = _(
                    "Community favors GE-Proton builds; Soda or Caffe is "
                    "the closest Bottles runner (x{evidence})"
                ).format(evidence=evidence)
                if not any("GE-Proton" in note for note in notes):
                    notes.append(ge_proton_note)
                continue

            if kind != "note_verb":
                continue

            trick = self.trick(value)
            if trick and "winetricks" not in attribution_sources:
                attribution_sources.append("winetricks")
            if trick and trick["bottles_dep"]:
                if not any(
                    dependency["name"] == trick["bottles_dep"]
                    for dependency in dependencies
                ):
                    dependencies.append(
                        {
                            "name": trick["bottles_dep"],
                            "evidence": evidence,
                            "reason": _(
                                "winetricks {verb} mentioned in reports"
                            ).format(verb=value),
                        }
                    )
                if "bottles_dependencies" not in attribution_sources:
                    attribution_sources.append("bottles_dependencies")
            elif trick:
                notes.append(
                    _(
                        "Reports mention winetricks verb '{verb}' (x{evidence})"
                    ).format(verb=value, evidence=evidence)
                )

        return {
            "match": hit["match"],
            "source": "protondb",
            "attributions": self.__attributions(*attribution_sources),
            "name": software["name"],
            "steam_appid": software["steam_appid"],
            "tier": software["tier"],
            "reports": software["reports"],
            "verdict_yes": software["verdict_yes"],
            "verdict_no": software["verdict_no"],
            "parameters": parameters,
            "env": env,
            "dll_overrides": dll_overrides,
            "args": args,
            "dependencies": dependencies,
            "notes": notes,
        }
