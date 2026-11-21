#!/usr/bin/env python3
# py-foliation, which changes the page labels of PDF documents.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
"""Install py-foliation to run with Python, on Linux, Windows or macOS (or remove it).

    python3 install.py [--version X] [--from FILE] [--no-gui] [--no-menu] [--uninstall]

It needs Python 3.14 or later, and only Python's standard library: install.sh
(Linux, macOS) and install.ps1 (Windows) find such a Python and run it.

* A Python environment of its own (venv), in the user's folders: no
  administrator rights are needed, and the system's Python is not touched.
  ~/.local/share/py-foliation (Linux; $XDG_DATA_HOME if set),
  ~/Library/Application Support/py-foliation (macOS), and
  %LOCALAPPDATA%\\py-foliation (Windows).
* In it, py-foliation with the window (PySide6) and pikepdf, from pip: the
  wheel of the latest release on GitHub (or Codeberg, if GitHub can't be
  reached), of --version X, or the wheel or folder given with --from.
* The commands py-foliation and py-foliation-gui: linked in ~/.local/bin
  (Linux, macOS), or their folder added to the user's PATH (Windows).
* The window in the applications menu (py-foliation-install), unless
  --no-menu.

Run it again to update to the latest release. --uninstall removes all of it
(the menu entry, the commands and the environment), and nothing else: the
settings and profiles (on macOS, in the same folder as the environment) stay.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

NAME = "py-foliation"
MINIMUM = (3, 14)
GITHUB = "https://github.com/nivaca/py-foliation"
CODEBERG = "https://codeberg.org/nivaca/py-foliation"
COMMANDS = ("py-foliation", "py-foliation-gui")
AGENT = {"User-Agent": "py-foliation-installer"}


def home_of_app() -> Path:
    """Where the environment goes."""
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / NAME
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / NAME


def scripts_of(venv: Path) -> Path:
    """The folder of the environment's commands."""
    return venv / ("Scripts" if sys.platform == "win32" else "bin")


def bin_folder() -> Path:
    """Where the commands are linked (Linux, macOS)."""
    return Path.home() / ".local" / "bin"


def wheel_name(version: str) -> str:
    return f"py_foliation-{version}-py3-none-any.whl"


def latest_version() -> str:
    """The version of the latest release: GitHub's (where /releases/latest leads), or else Codeberg's."""
    errors = []
    try:
        request = urllib.request.Request(f"{GITHUB}/releases/latest", headers=AGENT, method="HEAD")
        with urllib.request.urlopen(request, timeout=30) as answer:
            tag = answer.geturl().rstrip("/").rsplit("/", 1)[-1]
        if tag.startswith("v"):
            return tag[1:]
        errors.append(f"GitHub: no release ({answer.geturl()})")
    except OSError as e:
        errors.append(f"GitHub: {e}")
    try:
        api = CODEBERG.replace("codeberg.org/", "codeberg.org/api/v1/repos/") + "/releases/latest"
        with urllib.request.urlopen(urllib.request.Request(api, headers=AGENT), timeout=30) as answer:
            return json.load(answer)["tag_name"].lstrip("v")
    except (OSError, ValueError, KeyError) as e:
        errors.append(f"Codeberg: {e}")
    raise SystemExit("install.py: the latest release could not be found (" + "; ".join(errors) + ")")


def wheel_url(version: str) -> str:
    """The wheel of VERSION: on GitHub, or on Codeberg if GitHub doesn't answer."""
    for site in (GITHUB, CODEBERG):
        url = f"{site}/releases/download/v{version}/{wheel_name(version)}"
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers=AGENT, method="HEAD"), timeout=30).close()
            return url
        except OSError:
            continue
    raise SystemExit(f"install.py: there is no release {version} ({GITHUB}/releases)")


def requirement(source: str, gui: bool) -> str:
    """What pip installs: SOURCE (a wheel's URL or path, or a folder), with the window's extra if GUI."""
    extra = "[gui]" if gui else ""
    if "://" not in source:
        source = Path(source).resolve().as_uri()
    return f"{NAME}{extra} @ {source}"


def run(*command, quiet: bool = False) -> None:
    print("+", " ".join(str(c) for c in command), flush=True)
    result = subprocess.run([str(c) for c in command],
                            stdout=subprocess.DEVNULL if quiet else None)
    if result.returncode:
        raise SystemExit(f"install.py: this failed (exit code {result.returncode})")


def make_venv(venv: Path) -> Path:
    """The environment (made anew, so that an update starts clean), and its Python."""
    if venv.exists():
        shutil.rmtree(venv)
    try:
        import venv as venv_module  # (some Linux systems leave it out: python3-venv)
        venv_module.EnvBuilder(with_pip=True, upgrade_deps=False).create(venv)
    except (ImportError, subprocess.CalledProcessError, OSError) as e:
        raise SystemExit(f"install.py: a Python environment could not be made ({e}). On Debian and Ubuntu, "
                         f"install python3-venv (or python3.{sys.version_info[1]}-venv) and try again.") from None
    python = scripts_of(venv) / ("python.exe" if sys.platform == "win32" else "python")
    if not python.exists():
        raise SystemExit(f"install.py: the environment has no Python ({python})")
    return python


def link_commands(venv: Path) -> list[str]:
    """Make the commands reachable; what to tell the user about it."""
    notes = []
    if sys.platform == "win32":
        folder = str(scripts_of(venv))
        if add_to_user_path(folder):
            notes.append(f"{folder} was added to your PATH: open a new terminal to use py-foliation there.")
        return notes
    target = bin_folder()
    target.mkdir(parents=True, exist_ok=True)
    for command in COMMANDS:
        link = target / command
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(scripts_of(venv) / command)
    if str(target) not in os.environ.get("PATH", "").split(os.pathsep):
        notes.append(f"{target} is not on your PATH: add it (for instance, in ~/.profile or ~/.zshrc: "
                     f'export PATH="$HOME/.local/bin:$PATH") to type py-foliation in a terminal.')
    return notes


def add_to_user_path(folder: str) -> bool:
    """Add FOLDER to the user's PATH (Windows); whether it wasn't there."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            value, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            value, kind = "", winreg.REG_EXPAND_SZ
        parts = [p for p in value.split(";") if p]
        if any(os.path.normcase(p.rstrip("\\")) == os.path.normcase(folder.rstrip("\\")) for p in parts):
            return False
        winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts + [folder]))
    return True


def remove_from_user_path(folder: str) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            value, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return
        parts = [p for p in value.split(";")
                 if p and os.path.normcase(p.rstrip("\\")) != os.path.normcase(folder.rstrip("\\"))]
        winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))


def install(args) -> None:
    if args.source:
        source = args.source
    else:
        version = args.version or latest_version()
        source = wheel_url(version)
        print(f"py-foliation {version}: {source}")
    venv = home_of_app() / "venv"
    python = make_venv(venv)
    run(python, "-m", "pip", "install", "--disable-pip-version-check", requirement(source, not args.no_gui))
    notes = link_commands(venv)
    if not args.no_gui and not args.no_menu:
        run(python, "-m", "py_foliation.install")
    print()
    print(f"py-foliation is installed in {venv}.")
    if not args.no_gui:
        print("Start the window from the applications menu, or with py-foliation-gui; "
              "the command line is py-foliation.")
    for note in notes:
        print(note)


def uninstall() -> None:
    venv = home_of_app() / "venv"
    python = scripts_of(venv) / ("python.exe" if sys.platform == "win32" else "python")
    if python.exists():
        subprocess.run([str(python), "-m", "py_foliation.install", "--uninstall"])
    if sys.platform == "win32":
        remove_from_user_path(str(scripts_of(venv)))
    else:
        for command in COMMANDS:
            link = bin_folder() / command
            if link.is_symlink() and str(os.readlink(link)).startswith(str(venv)):
                link.unlink()
    # Only the environment: on macOS its folder also holds the settings and profiles.
    if venv.exists():
        shutil.rmtree(venv)
    try:
        home_of_app().rmdir()  # (if nothing else is left in it)
    except OSError:
        pass
    print("py-foliation is removed (your settings are kept).")


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MINIMUM:
        raise SystemExit("install.py: py-foliation needs Python %d.%d or later; this is %s (%s)"
                         % (MINIMUM + (sys.version.split()[0], sys.executable)))
    parser = argparse.ArgumentParser(prog="install.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--version", help="this release instead of the latest (e.g. 1.0.1)")
    parser.add_argument("--from", dest="source", metavar="FILE",
                        help="install this wheel, URL or source folder instead of a release")
    parser.add_argument("--no-gui", action="store_true", help="only the command line (no PySide6)")
    parser.add_argument("--no-menu", action="store_true", help="don't add the window to the applications menu")
    parser.add_argument("--uninstall", action="store_true", help="remove what this installed")
    args = parser.parse_args(argv)
    if args.uninstall:
        uninstall()
    else:
        install(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
