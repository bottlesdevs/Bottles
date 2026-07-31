import shlex

from bottles.backend.utils.terminal import TerminalUtils


GPU_ENV = {
    "DRI_PRIME": "1",
    "__NV_PRIME_RENDER_OFFLOAD": "1",
    "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
    "__VK_LAYER_NV_optimus": "NVIDIA_only",
    "VK_ICD_FILENAMES": "/graphics path/nvidia_icd.json",
}


def test_easyterm_keeps_gpu_environment_on_child_only(monkeypatch, mocker):
    terminal = TerminalUtils()
    terminal.terminal = terminal.terminals[0]
    mocker.patch.object(terminal, "check_support", return_value=True)
    popen = mocker.patch("bottles.backend.utils.terminal.subprocess.Popen")
    popen.return_value.communicate.return_value = (b"", None)
    monkeypatch.delenv("ENABLE_BASH", raising=False)
    command = "wine '/games/My Game.exe'"
    env = {**GPU_ENV, "KEEP_ME": "yes"}

    assert terminal.execute(command, env=env) is True

    full_command = popen.call_args.args[0]
    wrapper_env = popen.call_args.kwargs["env"]
    easyterm_args = shlex.split(full_command)
    child_args = shlex.split(easyterm_args[easyterm_args.index("-c") + 1])

    assert wrapper_env["KEEP_ME"] == "yes"
    assert all(key not in wrapper_env for key in GPU_ENV)
    assert child_args == [
        "env",
        *(f"{key}={value}" for key, value in GPU_ENV.items()),
        "bash",
        "-c",
        command,
    ]
    assert all(env[key] == value for key, value in GPU_ENV.items())


def test_other_terminals_keep_gpu_environment(mocker):
    terminal = TerminalUtils()
    terminal.terminal = ["kitty", "%s"]
    mocker.patch.object(terminal, "check_support", return_value=True)
    popen = mocker.patch("bottles.backend.utils.terminal.subprocess.Popen")
    popen.return_value.communicate.return_value = (b"", None)

    assert terminal.execute("wine game.exe", env=GPU_ENV.copy()) is True

    wrapper_env = popen.call_args.kwargs["env"]
    assert all(wrapper_env[key] == value for key, value in GPU_ENV.items())


def test_easyterm_interactive_bash_keeps_gpu_environment(monkeypatch, mocker):
    terminal = TerminalUtils()
    terminal.terminal = terminal.terminals[0]
    mocker.patch.object(terminal, "check_support", return_value=True)
    popen = mocker.patch("bottles.backend.utils.terminal.subprocess.Popen")
    popen.return_value.communicate.return_value = (b"", None)
    monkeypatch.setenv("ENABLE_BASH", "1")

    assert terminal.execute("ignored", env=GPU_ENV.copy()) is True

    full_command = popen.call_args.args[0]
    wrapper_env = popen.call_args.kwargs["env"]
    easyterm_args = shlex.split(full_command)
    child_args = shlex.split(easyterm_args[easyterm_args.index("-c") + 1])

    assert all(key not in wrapper_env for key in GPU_ENV)
    assert child_args == [
        "env",
        *(f"{key}={value}" for key, value in GPU_ENV.items()),
        "bash",
    ]
