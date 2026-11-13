"""Tests of the packaging: the versions agree, and the files that make the
RPM and the AppImage are sound."""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from py_foliation import __version__

ROOT = Path(__file__).resolve().parent.parent


def spec_field(name: str) -> str:
    m = re.search(rf"^{name}:\s*(\S+)", (ROOT / "packaging/py-foliation.spec").read_text(), re.M)
    return m.group(1) if m else ""


def test_versions_agree():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["version"] == __version__
    assert spec_field("Version") == __version__, "bump the spec: rpmdev-bumpspec -n VERSION"


def test_spec_changelog_has_this_version():
    changelog = (ROOT / "packaging/py-foliation.spec").read_text().split("%changelog", 1)[1]
    first = next(line for line in changelog.splitlines() if line.startswith("*"))
    assert first.rstrip().endswith(f"- {__version__}-{spec_field('Release').split('%')[0]}")


@pytest.mark.skipif(not shutil.which("desktop-file-validate"), reason="desktop-file-utils not installed")
def test_desktop_file():
    r = subprocess.run(["desktop-file-validate", str(ROOT / "packaging/py-foliation.desktop")],
                       capture_output=True, text=True)
    assert r.stdout + r.stderr == ""


def test_scripts_parse():
    assert subprocess.run(["bash", "-n", str(ROOT / "packaging/build-rpm.sh")]).returncode == 0
    for tool in ("release.py", "bundle-appimage.py", "icons.py", "screenshots.py", "manpage.py",
                 "flatpak-deps.py"):
        compile((ROOT / "tools" / tool).read_text(), tool, "exec")


@pytest.mark.skipif(not shutil.which("rpmspec"), reason="rpm-build not installed")
def test_spec_parses():
    r = subprocess.run(["rpmspec", "-q", "--srpm", "--qf", "%{version}", str(ROOT / "packaging/py-foliation.spec")],
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == __version__, r.stderr


def pinned_key() -> str:
    m = re.search(r'SIGNING_KEY="\$\{SIGNING_KEY:-([0-9A-F]{40})\}"', (ROOT / "packaging/build-rpm.sh").read_text())
    assert m, "build-rpm.sh must pin the project's signing key"
    return m.group(1)


@pytest.mark.skipif(not shutil.which("gpg"), reason="gpg not installed")
def test_the_shipped_key_is_the_pinned_one(tmp_path):
    r = subprocess.run(["gpg", "--batch", "--with-colons", "--show-keys",
                        str(ROOT / "packaging/RPM-GPG-KEY-py-foliation")],
                       capture_output=True, text=True, env={"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    fprs = [line.split(":")[9] for line in r.stdout.splitlines() if line.startswith("fpr:")]
    assert fprs and fprs[0] == pinned_key()


@pytest.mark.skipif(not all(shutil.which(t) for t in ("gpg", "git", "rpmbuild", "rpmspec")),
                    reason="gpg, git or rpm-build not installed")
def test_signing_without_the_key_says_how_to_import_it(tmp_path):
    """--sign uses only the pinned key: with an empty keyring it stops before building."""
    env = {"GNUPGHOME": str(tmp_path), "PATH": "/usr/bin:/bin", "RPMSIGN": "/bin/true"}
    r = subprocess.run(["bash", str(ROOT / "packaging/build-rpm.sh"), "--sign"], capture_output=True, text=True,
                       env=env)
    assert r.returncode == 1
    assert f"no secret key matching {pinned_key()}" in r.stderr and "gpg --import" in r.stderr


def test_manual_pages_are_up_to_date():
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "manpage.py"), "--check"], capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stderr


METAINFO = ROOT / "packaging/io.github.nivaca.py-foliation.metainfo.xml"


def test_metainfo_has_this_release():
    import xml.etree.ElementTree as ET
    releases = ET.parse(METAINFO).getroot().find("releases")
    assert releases[0].get("version") == __version__, "add the release to the metainfo"


@pytest.mark.skipif(not shutil.which("appstreamcli"), reason="appstream not installed")
def test_metainfo_is_valid():
    r = subprocess.run(["appstreamcli", "validate", "--no-net", str(METAINFO)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_flatpak_wheels_are_those_of_uv_lock():
    """python3-deps.json (tools/flatpak-deps.py) has the versions uv.lock has."""
    import json
    note = json.loads((ROOT / "packaging/flatpak/python3-deps.json").read_text())["x-note"]
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    versions = {p["name"]: p["version"] for p in lock["package"]}
    for name in ("pikepdf", "pillow", "lxml", "packaging"):
        assert f"{name} {versions[name]}" in note, f"{name}: run tools/flatpak-deps.py"
    manifest = (ROOT / "packaging/flatpak/io.github.nivaca.py-foliation.yml").read_text()
    assert "id: io.github.nivaca.py-foliation" in manifest and "python3-deps.json" in manifest
