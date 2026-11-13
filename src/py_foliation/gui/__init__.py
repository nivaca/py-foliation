"""The window of py-foliation (PySide6 / Qt 6).

Install with the ``gui`` extra (``pip install 'py-foliation[gui]'``) and
start with ``py-foliation-gui [file.pdf]``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ..interface import tr


def app_icon():
    """The program's icon, in every size that ships with it."""
    from PySide6.QtGui import QIcon

    icon = QIcon()
    hicolor = Path(__file__).resolve().parent.parent / "icons" / "linux" / "hicolor"
    for png in sorted(hicolor.glob("*/apps/py-foliation.png")):
        icon.addFile(str(png))
    return icon


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    from .. import interface
    from ..cli import interface_option  # (--interface CODE: this run only)

    interface.use_configured(interface_option(argv))
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(tr("The window needs PySide6. Install it with: pip install 'py-foliation[gui]'"), file=sys.stderr)
        return 1
    from .window import _WINDOWS, MainWindow, install_qt_translations

    app = QApplication.instance() or QApplication([sys.argv[0]] + argv)
    app.setApplicationName("py-foliation")
    app.setOrganizationName("py-foliation")
    # (the name of the menu entry: Wayland's app id; in the Flatpak, its id)
    app.setDesktopFileName(os.environ.get("FLATPAK_ID") or "py-foliation")
    app.setWindowIcon(app_icon())
    install_qt_translations()
    win = MainWindow()
    _WINDOWS.append(win)
    files = [a for a in argv if a.lower().endswith(".pdf")]
    if files:
        win.open_path(Path(files[0]))
    win.show()
    return app.exec()
