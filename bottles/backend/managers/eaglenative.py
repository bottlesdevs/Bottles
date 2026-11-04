# eaglenative.py
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
#
import json
import os
import selectors
import subprocess


def command(runner):
    if not runner:
        return None
    executable = os.path.join(runner, "bin", "eagle")
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        return None
    try:
        result = subprocess.run(
            [executable, "capabilities"], capture_output=True, text=True, timeout=5
        )
        data = json.loads(result.stdout)["data"]
        if (
            result.returncode == 0
            and data.get("schema") == 1
            and data.get("native_static_analyzer") is True
            and data.get("analysis", {}).get("available") is True
        ):
            return executable
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        pass
    return None


def analyze(executable, target, limit, progress, work, cancel=None):
    if cancel and cancel.is_set():
        raise RuntimeError("analysis cancelled")
    os.makedirs(work, exist_ok=True)
    environment = dict(os.environ, TMPDIR=work, TMP=work, TEMP=work)
    arguments = [executable, "analyze", target, "--scan-limit", str(limit), "--progress"]
    result = None
    pending = bytearray()
    errors = bytearray()
    with subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment) as process:
        try:
            with selectors.DefaultSelector() as selector:
                for stream in (process.stdout, process.stderr):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ)
                while selector.get_map():
                    if cancel and cancel.is_set():
                        raise RuntimeError("analysis cancelled")
                    for key, _ in selector.select(0.1):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        buffer = pending if key.fileobj is process.stdout else errors
                        buffer.extend(chunk)
                        if len(buffer) > 16 * 1024 * 1024:
                            raise ValueError("analysis output exceeds limit")
                        if buffer is errors:
                            continue
                        while b"\n" in pending:
                            line, _, remaining = pending.partition(b"\n")
                            pending[:] = remaining
                            message = json.loads(line)
                            if not isinstance(message, dict):
                                raise ValueError("invalid analysis response")
                            if result is not None:
                                raise ValueError("unexpected analysis response")
                            if message.get("event") == "step" and isinstance(message.get("data"), str):
                                progress(message["data"])
                            elif "event" not in message and isinstance(message.get("status"), bool):
                                result = message
                            else:
                                raise ValueError("unexpected analysis response")
                while process.poll() is None:
                    if cancel and cancel.is_set():
                        raise RuntimeError("analysis cancelled")
                    try:
                        process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        pass
            if cancel and cancel.is_set():
                raise RuntimeError("analysis cancelled")
            if process.returncode:
                error = errors.decode(errors="replace").strip()
                try:
                    failure = json.loads(error)
                    if isinstance(failure, dict) and isinstance(failure.get("error"), str):
                        error = failure["error"]
                except ValueError:
                    pass
                raise RuntimeError(error or "analysis failed")
            if pending or result is None:
                raise ValueError("incomplete analysis response")
            if not result["status"]:
                raise ValueError(result.get("error", "analysis failed"))
            if not isinstance(result.get("data"), dict):
                raise ValueError("invalid analysis report")
            return result["data"]
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=7)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
