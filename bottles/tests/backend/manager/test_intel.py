import sqlite3

import pytest

from bottles.backend.managers.eagle import EagleManager
from bottles.backend.managers import intel as intel_module
from bottles.backend.managers.intel import EagleIntel

SCHEMA = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE trick (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    title TEXT,
    files_json TEXT,
    overrides_json TEXT,
    winver TEXT,
    bottles_dep TEXT
);
CREATE TABLE software (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    steam_appid TEXT UNIQUE,
    trick_name TEXT,
    source TEXT NOT NULL
);
CREATE TABLE report_agg (
    software_id INTEGER PRIMARY KEY,
    reports INTEGER NOT NULL,
    verdict_yes INTEGER NOT NULL,
    verdict_no INTEGER NOT NULL,
    tinkered INTEGER NOT NULL,
    tier TEXT NOT NULL
);
CREATE TABLE tweak (
    software_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    evidence INTEGER NOT NULL
);
CREATE TABLE artifact (
    id INTEGER PRIMARY KEY,
    software_id INTEGER,
    sha256 TEXT,
    imphash TEXT
);
"""


def create_database(tmp_path, schema_version="1"):
    path = tmp_path / "eagle_intel.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
        (schema_version,),
    )
    connection.commit()
    return path, connection


def test_rejects_unsupported_schema(tmp_path):
    path, connection = create_database(tmp_path, schema_version="2")
    connection.close()

    intel = EagleIntel(str(path))

    assert not intel.available


def test_database_is_opened_read_only(tmp_path):
    path, connection = create_database(tmp_path)
    connection.close()
    intel = EagleIntel(str(path))

    with pytest.raises(sqlite3.OperationalError):
        intel._conn.execute("INSERT INTO meta (key, value) VALUES ('write', 'blocked')")

    intel.close()


def test_lookup_prefers_artifact_then_builds_protondb_plan(tmp_path):
    path, connection = create_database(tmp_path)
    connection.execute(
        "INSERT INTO software VALUES (1, 'Example Game', '1234', NULL, 'protondb')"
    )
    connection.execute("INSERT INTO report_agg VALUES (1, 100, 80, 20, 30, 'gold')")
    connection.execute(
        "INSERT INTO artifact VALUES (1, 1, 'known-sha', 'known-imphash')"
    )
    connection.executemany(
        "INSERT INTO tweak VALUES (1, ?, ?, ?)",
        [
            ("launch_flag", "enableNvapi", 8),
            ("launch_token", "DXVK_HUD=fps", 6),
            ("launch_token", "WINEDLLOVERRIDES=version=n,b", 6),
            ("launch_token", "WINEARCH=win32", 6),
            ("launch_token", "WINEPREFIX=/tmp/other", 6),
            ("launch_token", "DXVK_BAD=$(touch /tmp/file)", 6),
            ("launch_token", "--safe-mode", 5),
            ("launch_token", "--unsafe;command", 5),
        ],
    )
    connection.commit()
    connection.close()

    intel = EagleIntel(str(path))
    hit = intel.lookup(
        sha256="known-sha",
        steam_appid="wrong",
        product_name="Wrong Name",
    )
    plan = intel.plan(hit)

    assert hit["match"] == "sha256"
    assert plan["name"] == "Example Game"
    assert [item["name"] for item in plan["attributions"]] == ["ProtonDB"]
    assert [
        license_info["name"]
        for license_info in plan["attributions"][0]["licenses"]
    ] == ["ODbL 1.0", "DbCL 1.0"]
    assert plan["parameters"]["dxvk_nvapi"]["value"] is True
    assert plan["env"] == {"DXVK_HUD": {"value": "fps", "evidence": 6}}
    assert plan["dll_overrides"] == {
        "version": {"value": "n,b", "evidence": 6}
    }
    assert plan["args"] == [{"value": "--safe-mode", "evidence": 5}]

    suggestions = []
    EagleManager._merge_intel_suggestions(suggestions, plan)
    suggestions_by_key = {item["key"]: item["value"] for item in suggestions}
    assert suggestions_by_key["dxvk_nvapi"] is True
    assert suggestions_by_key["intel_env:DXVK_HUD"] == "fps"
    assert suggestions_by_key["intel_dll:version"] == "n,b"
    assert suggestions_by_key["intel_arg:--safe-mode"] == "--safe-mode"
    assert not any(item.get("apply", False) for item in suggestions)
    intel.close()


def test_exact_winetricks_match_builds_dependency_and_override_plan(tmp_path):
    path, connection = create_database(tmp_path)
    connection.execute(
        "INSERT INTO trick VALUES "
        "(1, 'example', 'apps', 'Example App', NULL, "
        '\'[{"mode":"native,builtin","dlls":["example.dll"]}]\', '
        "'win10', 'example-dependency')"
    )
    connection.execute(
        "INSERT INTO software VALUES (1, 'Example App', NULL, 'example', 'winetricks')"
    )
    connection.commit()
    connection.close()

    intel = EagleIntel(str(path))
    hit = intel.lookup(product_name="Example App")
    plan = intel.plan(hit)

    assert hit["match"] == "name"
    assert plan["source"] == "winetricks"
    assert [item["name"] for item in plan["attributions"]] == [
        "winetricks",
        "Bottles dependencies",
    ]
    assert plan["attributions"][0]["licenses"][0]["name"] == "LGPL-2.1-or-later"
    assert plan["attributions"][1]["licenses"] == []
    assert plan["dll_overrides"] == {"example.dll": {"value": "n,b", "evidence": 0}}
    assert plan["dependencies"][0]["name"] == "example-dependency"
    assert "Windows version to win10" in plan["notes"][1]
    intel.close()


def test_protondb_plan_credits_secondary_sources(tmp_path):
    path, connection = create_database(tmp_path)
    connection.execute(
        "INSERT INTO trick VALUES "
        "(1, 'example', 'dlls', 'Example Runtime', NULL, NULL, "
        "NULL, 'example-dependency')"
    )
    connection.execute(
        "INSERT INTO software VALUES (1, 'Example Game', '1234', NULL, 'protondb')"
    )
    connection.execute("INSERT INTO report_agg VALUES (1, 100, 80, 20, 30, 'gold')")
    connection.execute("INSERT INTO tweak VALUES (1, 'note_verb', 'example', 8)")
    connection.commit()
    connection.close()

    intel = EagleIntel(str(path))
    plan = intel.plan(intel.lookup(steam_appid="1234"))

    assert [item["name"] for item in plan["attributions"]] == [
        "ProtonDB",
        "winetricks",
        "Bottles dependencies",
    ]
    assert plan["dependencies"][0]["name"] == "example-dependency"
    intel.close()


def test_environment_database_override_is_discovered(monkeypatch, tmp_path):
    path, connection = create_database(tmp_path)
    connection.close()
    monkeypatch.setenv("EAGLE_INTEL_DB", str(path))

    intel = EagleIntel()

    assert intel.available
    assert intel.db_path == str(path)
    intel.close()


def test_packaged_database_is_used_when_user_database_is_missing(
    monkeypatch, tmp_path
):
    path, connection = create_database(tmp_path)
    connection.close()
    monkeypatch.delenv("EAGLE_INTEL_DB", raising=False)
    monkeypatch.setattr(intel_module.Paths, "base", str(tmp_path / "user"))
    monkeypatch.setattr(intel_module, "PACKAGED_DB_PATH", str(path))

    intel = EagleIntel()

    assert intel.available
    assert intel.db_path == str(path)
    intel.close()


def test_packaged_database_replaces_invalid_user_database(monkeypatch, tmp_path):
    user_dir = tmp_path / "user"
    packaged_dir = tmp_path / "packaged"
    user_dir.mkdir()
    packaged_dir.mkdir()
    user_path, connection = create_database(user_dir, schema_version="2")
    connection.close()
    packaged_path, connection = create_database(packaged_dir)
    connection.close()
    monkeypatch.delenv("EAGLE_INTEL_DB", raising=False)
    monkeypatch.setattr(intel_module.Paths, "base", str(user_dir))
    monkeypatch.setattr(intel_module, "PACKAGED_DB_PATH", str(packaged_path))

    intel = EagleIntel()

    assert intel.available
    assert intel.db_path == str(packaged_path)
    assert intel.db_path != str(user_path)
    intel.close()


def test_packaged_database_replaces_incomplete_user_database(monkeypatch, tmp_path):
    user_dir = tmp_path / "user"
    packaged_dir = tmp_path / "packaged"
    user_dir.mkdir()
    packaged_dir.mkdir()
    user_path, connection = create_database(user_dir)
    connection.execute("DROP TABLE tweak")
    connection.commit()
    connection.close()
    packaged_path, connection = create_database(packaged_dir)
    connection.close()
    monkeypatch.delenv("EAGLE_INTEL_DB", raising=False)
    monkeypatch.setattr(intel_module.Paths, "base", str(user_dir))
    monkeypatch.setattr(intel_module, "PACKAGED_DB_PATH", str(packaged_path))

    intel = EagleIntel()

    assert intel.available
    assert intel.db_path == str(packaged_path)
    assert intel.db_path != str(user_path)
    intel.close()


def test_conflicting_community_parameter_replaces_local_label():
    suggestions = [
        {
            "key": "sync",
            "value": "esync",
            "label": "Esync (threading)",
        }
    ]
    plan = {
        "parameters": {
            "sync": {
                "value": "wine",
                "evidence": 12,
                "reason": "community disables esync",
            }
        },
        "dependencies": [],
        "env": {},
        "dll_overrides": {},
        "args": [],
    }

    EagleManager._merge_intel_suggestions(suggestions, plan)

    assert suggestions == [
        {
            "key": "sync",
            "value": "wine",
            "label": "community disables esync (x12)",
            "apply": False,
        }
    ]


def test_generic_executable_name_does_not_fuzzy_match(tmp_path):
    path, connection = create_database(tmp_path)
    connection.execute(
        "INSERT INTO software VALUES "
        "(1, 'Game Launcher Deluxe', NULL, 'launcher', 'winetricks')"
    )
    connection.commit()
    connection.close()

    intel = EagleIntel(str(path))

    assert intel.lookup(names=["launcher"]) is None
    intel.close()


def test_generic_executable_name_does_not_exact_match(tmp_path):
    path, connection = create_database(tmp_path)
    connection.execute(
        "INSERT INTO software VALUES (1, 'Launcher', NULL, 'launcher', 'winetricks')"
    )
    connection.commit()
    connection.close()

    intel = EagleIntel(str(path))

    assert intel.lookup(names=["launcher"]) is None
    intel.close()


def test_fuzzy_match_normalizes_digit_boundaries(tmp_path):
    path, connection = create_database(tmp_path)
    connection.execute(
        "INSERT INTO software VALUES "
        "(1, 'Cyberpunk 2077', NULL, NULL, 'protondb')"
    )
    connection.execute("INSERT INTO report_agg VALUES (1, 20, 15, 5, 3, 'gold')")
    connection.commit()
    connection.close()

    intel = EagleIntel(str(path))
    hit = intel.lookup(names=["Cyberpunk2077"])

    assert hit["match"] == "fuzzy"
    assert hit["software"]["name"] == "Cyberpunk 2077"
    assert intel.lookup(names=["Cyberpnuk2077"])["match"] == "fuzzy"
    assert intel.lookup(names=["Cyberpunk2078"]) is None
    intel.close()


def test_finds_steam_appid_from_manifest(tmp_path):
    steamapps = tmp_path / "common" / "steamapps"
    game_dir = steamapps / "common" / "Example Game" / "bin"
    game_dir.mkdir(parents=True)
    executable = game_dir / "game.exe"
    executable.touch()
    (steamapps / "appmanifest_1234.acf").write_text(
        '"AppState"\n{\n"appid" "1234"\n"installdir" "Example Game"\n}'
    )

    assert EagleIntel.find_steam_appid(str(executable)) == "1234"
