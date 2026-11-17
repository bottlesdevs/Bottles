import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

import pyatspi


def visible_names(node):
    names = []
    if node.getState().contains(pyatspi.STATE_SHOWING) and node.name:
        names.append(node.name)
    for child in node:
        names.extend(visible_names(child))
    return names


results = []
output = Path("/results")
for mode in ("plain", "executable", "uri"):
    for attempt in range(3):
        name = f"startup-{mode}-{attempt + 1}"
        with tempfile.TemporaryDirectory(prefix=name) as directory:
            home = Path(directory)
            env = os.environ.copy()
            env.update(
                HOME=directory,
                XDG_DATA_HOME=str(home / "data"),
                XDG_CONFIG_HOME=str(home / "config"),
                XDG_CACHE_HOME=str(home / "cache"),
                GDK_BACKEND="x11",
                GSK_RENDERER="cairo",
                GTK_A11Y="atspi",
                LANGUAGE="en",
                LC_ALL="C.UTF-8",
                CPAK_CONTAINER_ID="startup-test",
            )
            fixture = home / "startup.exe"
            fixture.write_bytes(b"MZ")
            args = []
            if mode == "executable":
                args = ["--executable", str(fixture)]
            elif mode == "uri":
                args = [fixture.as_uri()]

            with (output / f"{name}.log").open("w") as log:
                process = subprocess.Popen(
                    ["/usr/bin/bottles", *args],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                names = []
                try:
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise AssertionError(
                                f"{name}: exited with {process.returncode}"
                            )
                        names = visible_names(pyatspi.Registry.getDesktop(0))
                        if "Welcome to Bottles" in names:
                            break
                        time.sleep(0.2)
                    subprocess.run(
                        ["import", "-window", "root", str(output / f"{name}.png")],
                        check=True,
                        timeout=10,
                    )
                    assert "Welcome to Bottles" in names, (name, names)
                    assert (home / "data/bottles/winebridge/WineBridge.exe").is_file()
                    results.append({"case": name, "visible_names": names})
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=5)
                    (output / "startup.json").write_text(json.dumps(results, indent=2))
            assert "Adwaita-CRITICAL" not in (output / f"{name}.log").read_text()

print(f"Fresh-profile startup passed: {len(results)} launches")
