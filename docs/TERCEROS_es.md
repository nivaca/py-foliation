Software libre que usa py-foliation
==================================

py-foliation tiene la licencia GNU General Public License, versión 3 o
posterior (GPL-3.0-or-later). Está hecho con el software libre que sigue,
y funciona sobre él. Las licencias se dan con sus identificadores SPDX,
tal como cada proyecto las declara; los textos completos vienen con cada
paquete.

Lo que el programa necesita para funcionar
------------------------------------------

| Software | Para qué se usa | Licencia |
|---|---|---|
| [Python](https://www.python.org) (3.14 o posterior) | el lenguaje en que está escrito | PSF-2.0 |
| [pikepdf](https://github.com/pikepdf/pikepdf) | lee y escribe los PDF | MPL-2.0 |
| [QPDF](https://github.com/qpdf/qpdf) | la biblioteca de PDF sobre la que trabaja pikepdf (en su wheel) | Apache-2.0 OR Artistic-2.0 |
| [libjpeg-turbo](https://libjpeg-turbo.org) | imágenes JPEG, para QPDF (en el wheel de pikepdf) | IJG AND BSD-3-Clause AND Zlib |
| [Pillow](https://python-pillow.github.io) | imágenes; lo requiere pikepdf | MIT-CMU |
| [lxml](https://lxml.de) | XML (los metadatos XMP); lo requiere pikepdf | BSD-3-Clause |
| [packaging](https://github.com/pypa/packaging) | números de versión; lo requiere pikepdf | Apache-2.0 OR BSD-2-Clause |

La ventana (el extra `gui`) necesita, además:

| Software | Para qué se usa | Licencia |
|---|---|---|
| [PySide6](https://doc.qt.io/qtforpython-6/) (pyside6-essentials, pyside6-pdf) | los enlaces de Qt para Python | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [Shiboken6](https://doc.qt.io/qtforpython-6/shiboken6/) | el soporte de los enlaces; lo requiere PySide6 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [Qt 6](https://www.qt.io) (en los wheels de PySide6) | la ventana, sus controles, y Qt PDF para las miniaturas | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| [PDFium](https://pdfium.googlesource.com/pdfium/) (dentro de Qt PDF) | dibuja las páginas de las miniaturas | BSD-3-Clause AND Apache-2.0 |

El RPM usa los paquetes de Fedora (python3-pikepdf, python3-pyside6,
qt6-qtbase, qpdf-libs), con las mismas licencias; Fedora da la de Qt y
PySide6 como LGPL-3.0-only OR GPL-3.0-only WITH Qt-GPL-exception-1.0.

Lo que sirve para construirlo, probarlo y empaquetarlo
------------------------------------------------------

Nada de esto queda instalado, salvo donde se indica.

| Software | Para qué se usa | Licencia |
|---|---|---|
| [uv](https://github.com/astral-sh/uv) y uv_build | el entorno del proyecto, y la construcción del wheel y del paquete fuente | MIT OR Apache-2.0 |
| [pytest](https://pytest.org) | las pruebas | MIT |
| [pluggy](https://github.com/pytest-dev/pluggy), [iniconfig](https://github.com/pytest-dev/iniconfig) | los requiere pytest | MIT |
| [Pygments](https://pygments.org) | lo requiere pytest | BSD-2-Clause |
| [colorama](https://github.com/tartley/colorama) | lo requiere pytest, en Windows | BSD-3-Clause |
| [python-appimage](https://github.com/niess/python-appimage) | el Python reubicable que lleva la AppImage (Python 3.15; contiene Python, bajo PSF-2.0) | GPL-3.0 |
| [appimagetool](https://github.com/AppImage/appimagetool) | hace la AppImage | MIT |
| [Inkscape](https://inkscape.org) | dibuja los iconos a partir de su SVG (`tools/icons.py`) | GPL-2.0-or-later |
| [fontTools](https://github.com/fonttools/fonttools) | su lista de glifos asigna caracteres a los nombres de glifo, en `tools/fontmetrics.py` | MIT |
| [URW base 35 fonts](https://github.com/ArtifexSoftware/urw-base35-fonts) | sus archivos AFM dan los anchos de caracteres de `fontmetrics.py` (solo se guardan los anchos; no se distribuye ninguna fuente) | AGPL-3.0-only AND GPL-2.0-or-later (según Fedora) |

Las versiones en uso son las de `uv.lock`; las licencias se comprobaron
en los metadatos de los paquetes instalados (pikepdf 10.18, PySide6 6.12,
Pillow 13, lxml 6.1, pytest 9.2) y en los de Fedora 45.
