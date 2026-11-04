import os
from pathlib import Path
import subprocess
import sys

from bottles.backend.models.config import BottleConfig
from bottles.backend.utils.manager import ManagerUtils
from bottles.backend.wine.regkeys import RegKeys

runner = Path(sys.argv[1])
prefix = Path(sys.argv[2])
os.environ.update(
    WINEPREFIX=str(prefix), WINEARCH="win64", WINEDEBUG="-all",
    WINEDLLOVERRIDES="mscoree,mshtml=",
)
ManagerUtils.set_external_runner_paths({"dpi-test": str(runner.parent.parent)})
config = BottleConfig(
    Name="DPI test", Path=str(prefix), Custom_Path=True, Runner="dpi-test",
    Environment="Custom",
    Environment_Variables={"WINEDLLOVERRIDES": "mscoree,mshtml=", "WINEDEBUG": "-all"},
)
key = r"HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"


def run(*args):
    return subprocess.run([str(runner), *args], check=True, capture_output=True, text=True, timeout=90)


try:
    run("wineboot", "-u")
    seed = prefix / "drive_c/.dpi-test.reg"
    seed.write_text(
        f'Windows Registry Editor Version 5.00\n\n[{key}]\n@="~ RUNASADMIN HIGHDPIAWARE"\n"game.exe"="DPIUNAWARE"\n',
        encoding="utf-16",
    )
    run("reg", "import", r"C:\.dpi-test.reg")
    for mode, flags in (
        ("system", "~ RUNASADMIN DPIUNAWARE"),
        ("application", "~ RUNASADMIN HIGHDPIAWARE"),
        ("default", "~ RUNASADMIN"),
    ):
        result = RegKeys(config).set_dpi_scaling(mode)
        assert result.ok, (mode, result.message, result.data)
        selected = RegKeys(config).get_dpi_scaling()
        assert selected.ok and selected.data == mode, (mode, selected.message, selected.data)
        assert flags in run("reg", "query", key, "/ve").stdout
        assert "DPIUNAWARE" in run("reg", "query", key, "/v", "game.exe").stdout
    run("reg", "add", key, "/ve", "/t", "REG_SZ", "/d", "~ HIGHDPIAWARE", "/f")
    result = RegKeys(config).set_dpi_scaling("default")
    assert result.ok, result.message
    run("reg", "export", key, r"C:\.dpi-test.reg", "/y")
    assert not any(line.startswith("@=") for line in seed.read_text(encoding="utf-16").splitlines())
    assert not list((prefix / "drive_c").glob(".bottles-dpi-*"))
    print("DPI modes preserve other flags and per-program rules; Default removes the DPI override")
finally:
    subprocess.run([str(runner.parent / "wineserver"), "-k"], timeout=15)
    subprocess.run([str(runner.parent / "wineserver"), "-w"], timeout=15)
