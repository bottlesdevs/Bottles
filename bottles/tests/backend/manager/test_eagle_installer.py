import shutil
import subprocess
from types import SimpleNamespace

import pytest

from bottles.backend.managers import eagle as eagle_module
from bottles.backend.managers.eagle import EagleManager


@pytest.mark.parametrize("architecture", ["i686", "x86_64"])
def test_msi_file_ids_without_extensions(monkeypatch, tmp_path, architecture):
    compiler = shutil.which(f"{architecture}-w64-mingw32-gcc")
    if not compiler or not shutil.which("wixl") or not shutil.which("7z"):
        pytest.skip("MinGW, wixl and 7z required")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    subprocess.run([compiler, str(source), "-o", str(tmp_path / "sample.exe")], check=True, capture_output=True)
    (tmp_path / "note.txt").write_text("Not an executable")
    wix = tmp_path / "package.wxs"
    wix.write_text('<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">'
        '<Product Id="*" Name="Fixture" Language="1033" Version="1.0.0" Manufacturer="Example" '
        'UpgradeCode="115D7030-2F9F-4F82-AB60-AD34E63B86D8">'
        '<Package InstallerVersion="200" Compressed="yes"/>'
        '<Media Id="1" Cabinet="payload.cab" EmbedCab="yes"/>'
        '<Directory Id="TARGETDIR" Name="SourceDir"><Directory Id="ProgramFilesFolder">'
        '<Directory Id="INSTALLDIR" Name="Fixture"><Component Id="Main" Guid="*">'
        '<File Id="App" Source="sample.exe" KeyPath="yes"/><File Id="Note" Source="note.txt"/>'
        '</Component></Directory></Directory></Directory>'
        '<Feature Id="MainFeature" Level="1"><ComponentRef Id="Main"/></Feature></Product></Wix>')
    target = tmp_path / "package.msi"
    subprocess.run(["wixl", "-o", str(target), str(wix)], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setattr(eagle_module, "Paths", SimpleNamespace(temp=str(tmp_path)))
    manager = EagleManager.__new__(EagleManager)
    manager._send_step = lambda *_args, **_kwargs: None
    files, output = manager._extract_installer(str(target), "MSI")
    try:
        assert len(files) == 1
        with open(files[0], "rb") as stream:
            assert stream.read() == (tmp_path / "sample.exe").read_bytes()
    finally:
        manager._cleanup_extraction(output)


@pytest.mark.parametrize("member", ["app.exe", "APP.EXE", "App.ExE"])
def test_nsis_member_extension_case(monkeypatch, tmp_path, member):
    compiler = shutil.which("x86_64-w64-mingw32-gcc")
    if not compiler or not shutil.which("makensis") or not shutil.which("7z"):
        pytest.skip("MinGW, NSIS and 7z required")
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n")
    payload = tmp_path / "payload.exe"
    subprocess.run([compiler, str(source), "-o", str(payload)], check=True, capture_output=True)
    target = tmp_path / "installer.exe"
    script = tmp_path / "package.nsi"
    script.write_text(f'Name "Fixture"\nOutFile "{target}"\nSection\nSetOutPath "$INSTDIR"\n'
        f'File /oname={member} "{payload}"\nFile /oname=Library.DlL "{payload}"\nSectionEnd\n')
    subprocess.run(["makensis", "-V2", str(script)], check=True, capture_output=True)
    monkeypatch.setattr(eagle_module, "Paths", SimpleNamespace(temp=str(tmp_path)))
    manager = EagleManager.__new__(EagleManager)
    manager._send_step = lambda *_args, **_kwargs: None
    files, output = manager._extract_installer(str(target), "NSIS")
    try:
        assert [eagle_module.os.path.basename(path) for path in files] == [member, "Library.DlL"]
        for path in files:
            with open(path, "rb") as stream:
                assert stream.read() == payload.read_bytes()
    finally:
        manager._cleanup_extraction(output)
