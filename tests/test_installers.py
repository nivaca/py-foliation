"""The installers of installers/ (to run py-foliation with Python on Linux, Windows and macOS).

Nothing here downloads or installs anything: the folders, what pip is given, and that removing it
takes away what it added and nothing else (in a home of the test's own)."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INSTALLERS = ROOT / "installers"


@pytest.fixture()
def installer(monkeypatch, tmp_path):
    """installers/install.py, imported, with a home of its own (and no XDG folders of the user's)."""
    for name in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "LOCALAPPDATA", "APPDATA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    spec = importlib.util.spec_from_file_location("installer_under_test", INSTALLERS / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_installers_are_there():
    for name in ("install.py", "install.sh", "install.ps1"):
        assert (INSTALLERS / name).is_file(), name
    assert os.access(INSTALLERS / "install.sh", os.X_OK) and os.access(INSTALLERS / "install.py", os.X_OK)
    if shutil.which("sh"):
        assert subprocess.run(["sh", "-n", str(INSTALLERS / "install.sh")]).returncode == 0
    for name in ("install.sh", "install.ps1"):
        text = (INSTALLERS / name).read_text()
        assert "(3, 14)" in text and "installers/install.py" in text  # (the same Python, the same script)


def test_folders_of_each_system(installer, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    assert installer.home_of_app() == tmp_path / ".local" / "share" / "py-foliation"
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert installer.home_of_app() == tmp_path / "data" / "py-foliation"
    assert installer.scripts_of(Path("v")) == Path("v") / "bin"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert installer.home_of_app() == tmp_path / "Library" / "Application Support" / "py-foliation"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert installer.home_of_app() == tmp_path / "Local" / "py-foliation"
    assert installer.scripts_of(Path("v")) == Path("v") / "Scripts"


def test_what_pip_is_given(installer, tmp_path):
    url = "https://github.com/nivaca/py-foliation/releases/download/v1.0.1/py_foliation-1.0.1-py3-none-any.whl"
    assert installer.wheel_name("1.0.1") == "py_foliation-1.0.1-py3-none-any.whl"
    assert installer.requirement(url, True) == f"py-foliation[gui] @ {url}"
    assert installer.requirement(url, False) == f"py-foliation @ {url}"
    wheel = tmp_path / "py_foliation-1.0.1-py3-none-any.whl"
    assert installer.requirement(str(wheel), True) == f"py-foliation[gui] @ {wheel.as_uri()}"


def test_too_old_a_python(installer, monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 13, 0))
    with pytest.raises(SystemExit, match="3.14 or later"):
        installer.main([])


@pytest.mark.skipif(sys.platform == "win32", reason="the links are for Linux and macOS")
def test_links_and_removal(installer, monkeypatch, tmp_path):
    """The commands are linked in ~/.local/bin; --uninstall removes them and the environment, and
    leaves what else is in its folder (on macOS, the settings and profiles), and other links."""
    monkeypatch.setattr(sys, "platform", "linux")
    venv = installer.home_of_app() / "venv"
    (venv / "bin").mkdir(parents=True)
    for command in installer.COMMANDS:
        (venv / "bin" / command).write_text("#!/bin/sh\n")
    keep = installer.home_of_app() / "profiles.json"
    keep.write_text("{}")
    other = installer.bin_folder() / "other-tool"
    installer.bin_folder().mkdir(parents=True)
    other.symlink_to(tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    notes = installer.link_commands(venv)
    assert notes and ".local/bin" in notes[0]  # (not on the PATH: said how to add it)
    for command in installer.COMMANDS:
        link = installer.bin_folder() / command
        assert link.is_symlink() and Path(os.readlink(link)) == venv / "bin" / command
    installer.uninstall()
    assert not venv.exists() and keep.exists() and other.is_symlink()
    assert not any((installer.bin_folder() / c).is_symlink() for c in installer.COMMANDS)
    keep.unlink()
    installer.uninstall()  # (again, with nothing left: no error, and the empty folder goes)
    assert not installer.home_of_app().exists()
