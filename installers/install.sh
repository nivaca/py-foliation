#!/bin/sh
# py-foliation, which changes the page labels of PDF documents.
# Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. This program is distributed WITHOUT ANY
# WARRANTY; see the LICENSE file, or <https://www.gnu.org/licenses/>.
#
# Installs py-foliation to run with Python, on Linux or macOS:
#
#   curl -LsSf https://raw.githubusercontent.com/nivaca/py-foliation/main/installers/install.sh | sh
#   sh install.sh [--version X] [--no-gui] [--no-menu] [--uninstall]
#   (with curl ... | sh -s -- --uninstall, the options go after "-s --")
#
# It finds Python 3.14 or later and runs install.py with it (the one next to
# this script, or else the one in the repository): see install.py for what
# is installed, and where.
set -eu

URL="https://raw.githubusercontent.com/nivaca/py-foliation/main/installers/install.py"

python=""
for candidate in python3.17 python3.16 python3.15 python3.14 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 14))' 2>/dev/null; then
        python="$candidate"
        break
    fi
done
if [ -z "$python" ]; then
    echo "install.sh: py-foliation needs Python 3.14 or later, and none was found." >&2
    case "$(uname -s)" in
        Darwin) echo "Install it from https://www.python.org/downloads/macos/ (or: brew install python@3.14)." >&2 ;;
        *) echo "Install it with your system's packages (python3.14), or from https://www.python.org/downloads/." >&2 ;;
    esac
    exit 1
fi

here="$(cd "$(dirname "$0")" 2>/dev/null && pwd || true)"
if [ -n "$here" ] && [ -f "$here/install.py" ]; then
    exec "$python" "$here/install.py" "$@"
fi
script="$(mktemp "${TMPDIR:-/tmp}/py-foliation-install.XXXXXX")"
trap 'rm -f "$script"' EXIT
if command -v curl >/dev/null 2>&1; then
    curl -LsSf "$URL" -o "$script"
elif command -v wget >/dev/null 2>&1; then
    wget -q "$URL" -O "$script"
else
    "$python" -c "import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" "$URL" "$script"
fi
"$python" "$script" "$@"
