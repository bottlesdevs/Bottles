import json
import os
import shlex
import subprocess
import threading

from bottles.backend.models.result import Result
from bottles.backend.state import SignalManager, Signals
from bottles.backend.utils.manager import ManagerUtils

ANALYSIS_TIMEOUT = 600
TERMINATE_TIMEOUT = 5

def backend(config):
    runner = config.get("RunnerPath") or ManagerUtils.get_runner_path(config.get("Runner", ""))
    if not runner:
        return None
    executable = os.path.join(runner, "bin", "eagle")
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        return None
    return executable

def trace_command(config, runner, cwd):
    wine = shlex.split(runner)[0]
    selected = dict(config, RunnerPath=os.path.dirname(os.path.dirname(wine)))
    executable = backend(selected)
    if not tracing_supported(selected):
        raise RuntimeError('The selected runner does not include Eagle tracing')
    prefix = ManagerUtils.get_bottle_path(config)
    return shlex.join([executable, 'trace', '--wine', wine, '--prefix', prefix, '--logs', os.path.join(prefix, 'logs', 'runs'), '--cwd', cwd, '--'])

def tracing_supported(config):
    executable = backend(config)
    if not executable:
        return False
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(executable)), 'share', 'eagle', 'providers.json')
        with open(path) as file:
            manifest = json.loads(file.read(65537))
        return manifest.get('tracing') == 1 and all(
            set(manifest.get('profiles', {}).get(name, [])) >= {'32', '64'}
            for name in ('winrt', 'dwrite', 'com', 'wait')
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False

def security_scan(config, executable_path):
    executable = backend(config)
    if not executable:
        return None
    result = subprocess.run([executable, 'security-scan', executable_path], capture_output=True, text=True, timeout=35)
    if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
        raise RuntimeError('Eagle backend scan failed')
    response = json.loads(result.stdout)
    if not isinstance(response, dict) or not response.get('status') or not isinstance(response.get('data'), list):
        raise ValueError('Invalid Eagle scan response')
    return response['data']

def analyze(config, executable_path, scan_limit):
    executable = backend(config)
    if not executable:
        return False
    finished = None
    with subprocess.Popen(
        [executable, "analyze", "--progress", "--scan-limit", str(scan_limit), executable_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ) as process:
        def terminate():
            process.terminate()
            try:
                process.wait(timeout=TERMINATE_TIMEOUT)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=TERMINATE_TIMEOUT)
        timer = threading.Timer(ANALYSIS_TIMEOUT, terminate)
        timer.daemon = True
        timer.start()
        try:
            while line := process.stdout.readline(2 * 1024 * 1024 + 1):
                if len(line) > 2 * 1024 * 1024:
                    raise ValueError("Eagle backend response exceeds size limit")
                response = json.loads(line)
                if not isinstance(response, dict):
                    raise ValueError("Invalid Eagle backend response")
                if response.get("event") == "step":
                    SignalManager.send(Signals.EagleStep, Result(status=True, data=response["data"]))
                elif "status" in response:
                    finished = response
            if process.wait(timeout=10) or finished is None:
                raise RuntimeError("Eagle backend analysis failed")
        finally:
            timer.cancel()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    SignalManager.send(Signals.EagleFinished, Result(status=finished["status"], data=finished.get("data", {"error": finished.get("error")})))
    return True
