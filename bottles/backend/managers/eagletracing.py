# eagletracing.py
#
# Copyright 2025 mirkobrombin <brombin94@gmail.com>
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
#
import json
import os
import re
import shlex

from bottles.backend.utils.manager import ManagerUtils


def tracing_supported(config, wine=None):
    match = re.match(
        r"^soda-(\d+)\.(\d+)-(\d+)(?:-|$)", config.get("Runner", ""), re.IGNORECASE
    )
    if not match or tuple(map(int, match.groups())) < (11, 0, 26):
        return False
    if wine:
        runner = os.path.dirname(os.path.dirname(shlex.split(wine)[0]))
    elif config.get("Environment") == "Steam":
        runner = config.get("RunnerPath", "")
    else:
        runner = ManagerUtils.get_runner_path(config.get("Runner", ""))
    if not runner:
        return False
    executable = os.path.join(runner, "bin", "eagle")
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        return False
    try:
        with open(os.path.join(runner, "share", "eagle", "providers.json")) as file:
            manifest = json.loads(file.read(65537))
        return manifest.get("tracing") == 1 and all(
            set(manifest.get("profiles", {}).get(name, [])) >= {"32", "64"}
            for name in ("winrt", "dwrite", "com", "wait")
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def trace_command(config, wine, cwd):
    if not tracing_supported(config, wine):
        raise RuntimeError("The selected runner does not include Eagle tracing")
    wine = shlex.split(wine)[0]
    executable = os.path.join(os.path.dirname(os.path.dirname(wine)), "bin", "eagle")
    prefix = ManagerUtils.get_bottle_path(config)
    return shlex.join([
        executable, "trace", "--wine", wine, "--prefix", prefix,
        "--logs", os.path.join(prefix, "logs", "runs"), "--cwd", cwd, "--",
    ])
