Open-source software used by py-foliation
=========================================

py-foliation itself is licensed under the GNU General Public License,
version 3 or later (GPL-3.0-or-later). It is made with, and runs on, the
following open-source software. The licences are given as SPDX
identifiers, as each project declares them; the full texts come with
each package.

What the program needs to run
-----------------------------

| Software | What it is used for | Licence |
|---|---|---|
| [Python](https://www.python.org) (3.14 or later) | the language the program is written in | PSF-2.0 |
| [pikepdf](https://github.com/pikepdf/pikepdf) | reads and writes the PDF files | MPL-2.0 |
| [QPDF](https://github.com/qpdf/qpdf) | the PDF library under pikepdf (in its wheel) | Apache-2.0 OR Artistic-2.0 |
| [libjpeg-turbo](https://libjpeg-turbo.org) | JPEG images, for QPDF (in pikepdf's wheel) | IJG AND BSD-3-Clause AND Zlib |
| [Pillow](https://python-pillow.github.io) | images, required by pikepdf | MIT-CMU |
| [lxml](https://lxml.de) | XML (the XMP metadata), required by pikepdf | BSD-3-Clause |
| [packaging](https://github.com/pypa/packaging) | version numbers, required by pikepdf | Apache-2.0 OR BSD-2-Clause |

The window (the `gui` extra) needs, besides:

| Software | What it is used for | Licence |
|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython-6/) (pyside6-essentials, pyside6-pdf) | the Python bindings of Qt | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [Shiboken6](https://doc.qt.io/qtforpython-6/shiboken6/) | the binding generator's runtime, required by PySide6 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [Qt 6](https://www.qt.io) (in the PySide6 wheels) | the window, its widgets, and Qt PDF for the thumbnails | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [PDFium](https://pdfium.googlesource.com/pdfium/) (inside Qt PDF) | draws the pages of the thumbnails | BSD-3-Clause AND Apache-2.0 |

The RPM uses Fedora's own packages of these (python3-pikepdf,
python3-pyside6, qt6-qtbase, qpdf-libs), whose licences are the same;
Fedora gives Qt and PySide6 as LGPL-3.0-only OR GPL-3.0-only WITH
Qt-GPL-exception-1.0.

What builds, tests and packages it
----------------------------------

None of these is part of what is installed, except where it says so.

| Software | What it is used for | Licence |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) and uv_build | the project's environment, and building the wheel and the source package | MIT OR Apache-2.0 |
| [pytest](https://pytest.org) | the tests | MIT |
| [pluggy](https://github.com/pytest-dev/pluggy), [iniconfig](https://github.com/pytest-dev/iniconfig) | required by pytest | MIT |
| [Pygments](https://pygments.org) | required by pytest | BSD-2-Clause |
| [colorama](https://github.com/tartley/colorama) | required by pytest, on Windows | BSD-3-Clause |
| [python-appimage](https://github.com/niess/python-appimage) | the relocatable Python carried by the AppImage (Python 3.15; it holds Python, under PSF-2.0) | GPL-3.0 |
| [appimagetool](https://github.com/AppImage/appimagetool) | makes the AppImage | MIT |
| [Inkscape](https://inkscape.org) | draws the icons from their SVG (`tools/icons.py`) | GPL-2.0-or-later |
| [fontTools](https://github.com/fonttools/fonttools) | its glyph list maps glyph names to characters, in `tools/fontmetrics.py` | MIT |
| [URW base 35 fonts](https://github.com/ArtifexSoftware/urw-base35-fonts) | their AFM files give the character widths of `fontmetrics.py` (only the widths are kept, no font is shipped) | AGPL-3.0-only AND GPL-2.0-or-later (as Fedora gives it) |

The versions in use are those of `uv.lock`; the licences above were
checked against the metadata of the installed packages (pikepdf 10.18,
PySide6 6.12, Pillow 13, lxml 6.1, pytest 9.2) and of Fedora 45.
