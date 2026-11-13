#!/usr/bin/env python3
"""Make packaging/flatpak/python3-deps.json, the module of the Flatpak that
installs what py-foliation needs from PyPI (pikepdf and its dependencies, at
the versions of uv.lock) and, for the build only, uv_build:

    python3 tools/flatpak-deps.py [--python 3.13]

Flatpaks are built without the network, so each wheel is listed with its
address and checksum, for each architecture Flathub builds (x86_64 and
aarch64). PYTHON is the Python of the Flatpak's runtime (org.kde.Platform);
the wheels must be made for it. PySide6 comes with the base app
(io.qt.PySide.BaseApp), not from here.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "flatpak" / "python3-deps.json"
ARCHES = ["x86_64", "aarch64"]
TOP = "pikepdf"  # (what py-foliation needs from PyPI, besides PySide6)
BUILD_BACKEND = ("uv_build", ">=0.10,<0.14")  # (as pyproject.toml's build-system)


def locked_versions() -> dict[str, str]:
    """TOP and what it needs, at the versions of uv.lock."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    packages = {p["name"]: p for p in lock["package"]}
    out: dict[str, str] = {}

    def walk(name):
        if name in out:
            return
        out[name] = packages[name]["version"]
        for dep in packages[name].get("dependencies", []):
            walk(dep["name"])

    walk(TOP)
    return out


def pypi(name: str, version: str | None = None) -> dict:
    url = f"https://pypi.org/pypi/{name}/{version}/json" if version else f"https://pypi.org/pypi/{name}/json"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def fits(filename: str, arch: str, py: tuple[int, int]) -> bool:
    """Can a Python PY on Linux/ARCH (glibc) install this wheel?"""
    m = re.fullmatch(r"[^-]+-[^-]+(?:-\d[^-]*)?-([^-]+)-([^-]+)-([^-]+)\.whl", filename)
    if not m:
        return False
    pytags, abis, plats = (x.split(".") for x in m.groups())
    plat_ok = any(p == "any" or (p.startswith("manylinux") and p.endswith("_" + arch)) for p in plats)
    cp = f"cp{py[0]}{py[1]}"
    py_ok = any(t in ("py3", cp) or (t.startswith("cp3") and "abi3" in abis and int(t[3:]) <= py[1])
                for t in pytags)
    abi_ok = any(a in ("none", "abi3", cp) for a in abis)
    return plat_ok and py_ok and abi_ok


def wheels(name: str, version: str, py: tuple[int, int]) -> list[dict]:
    files = pypi(name, version)["urls"]
    out = []
    for arch in ARCHES:
        found = [f for f in files if f["packagetype"] == "bdist_wheel" and fits(f["filename"], arch, py)]
        if not found:
            sys.exit(f"no wheel of {name} {version} for Python {py[0]}.{py[1]} on {arch}")
        f = sorted(found, key=lambda f: f["filename"])[-1]
        source = {"type": "file", "url": f["url"], "sha256": f["digests"]["sha256"]}
        if not f["filename"].endswith("-any.whl"):
            source["only-arches"] = [arch]
        if source not in out:
            out.append(source)
    return out


def backend_version() -> str:
    name, spec = BUILD_BACKEND
    low, high = re.findall(r"[\d.]+", spec)

    def key(v):
        return tuple(int(x) for x in v.split("."))

    releases = [v for v in pypi(name)["releases"] if re.fullmatch(r"[\d.]+", v)
                and key(low) <= key(v) < key(high)]
    return max(releases, key=key)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make the Python module of the Flatpak.")
    parser.add_argument("--python", default="3.13", help="the Python of the runtime (default: 3.13)")
    args = parser.parse_args(argv)
    py = tuple(int(x) for x in args.python.split("."))[:2]
    versions = locked_versions()
    deps = {"name": "python3-deps", "buildsystem": "simple",
            "build-commands": ['pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
                               '--prefix=${FLATPAK_DEST} --no-build-isolation ' + " ".join(sorted(versions))],
            "sources": [s for name, v in sorted(versions.items()) for s in wheels(name, v, py)]}
    backend = backend_version()
    build = {"name": "python3-uv-build", "buildsystem": "simple",
             "build-commands": ['pip3 install --verbose --no-index --find-links="file://${PWD}" '
                                '--prefix=${FLATPAK_DEST} uv_build'],
             "cleanup": ["*"],  # (only for building py-foliation: not in the app)
             "sources": wheels("uv_build", backend, py)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    note = (f"Made by tools/flatpak-deps.py --python {args.python}: "
            + ", ".join(f"{n} {v}" for n, v in sorted(versions.items())) + f"; uv_build {backend} (build only)")
    OUT.write_text(json.dumps({"name": "python3-modules", "buildsystem": "simple", "build-commands": [],
                               "modules": [deps, build], "x-note": note}, indent=2) + "\n")
    print(f"Wrote {OUT.relative_to(ROOT)}: {note}")


if __name__ == "__main__":
    main()
