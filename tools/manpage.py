#!/usr/bin/env python3
"""Hace las páginas de manual de py-foliation a partir de la ayuda de su línea de órdenes:

    uv run python tools/manpage.py [--check]

Escribe packaging/man/py-foliation.1 (en inglés) y packaging/man/es/py-foliation.1 (en
español), que instala el RPM. Cada una trae la ayuda del programa y la de cada orden, tal
como las imprime la línea de órdenes, de modo que el manual no puede decir nada que el
programa no diga. --check solo dice si los archivos están al día (lo usan las pruebas).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
MAN = ROOT / "packaging" / "man"

# The headings of the page, in each language
HEADINGS = {
    "en": {"name": "NAME", "synopsis": "SYNOPSIS", "description": "DESCRIPTION", "commands": "COMMANDS",
           "files": "FILES", "see": "SEE ALSO", "author": "AUTHOR",
           "summary": "change the page labels of PDF documents",
           "files_text": "The configuration file, with the language of the interface: "
                         "~/.config/py-foliation/config.toml (or $PY_FOLIATION_CONFIG/config.toml).",
           "window": "The window: py-foliation-gui [file.pdf]."},
    "es": {"name": "NOMBRE", "synopsis": "SINOPSIS", "description": "DESCRIPCIÓN", "commands": "ÓRDENES",
           "files": "ARCHIVOS", "see": "VÉASE TAMBIÉN", "author": "AUTOR",
           "summary": "cambiar las etiquetas de página de documentos PDF",
           "files_text": "El archivo de configuración, con el idioma de la interfaz: "
                         "~/.config/py-foliation/config.toml (o $PY_FOLIATION_CONFIG/config.toml).",
           "window": "La ventana: py-foliation-gui [archivo.pdf]."},
}


def roff(text: str) -> str:
    """TEXT safe in roff: backslashes doubled, and no line starting with . or '."""
    out = []
    for line in text.replace("\\", "\\e").splitlines():
        out.append("\\&" + line if line.startswith((".", "'")) else line)
    return "\n".join(out)


def page(lang: str) -> str:
    from py_foliation import __version__, interface
    from py_foliation.cli import build_parser
    from py_foliation.completion import commands

    interface.use(lang)
    interface.translate_argparse()
    os.environ.update(COLUMNS="78", NO_COLOR="1", PYTHON_COLORS="0")  # (the same text in and out of a terminal)
    h = HEADINGS[lang]
    parser = build_parser()
    parser.formatter_class = argparse.HelpFormatter
    lines = [f'.TH PY-FOLIATION 1 "" "py-foliation {__version__}" "py-foliation"',
             f".SH {h['name']}", f"py-foliation \\- {h['summary']}",
             f".SH {h['synopsis']}", ".nf", roff(parser.format_usage().split(" ", 1)[1].strip()), ".fi",
             f".SH {h['description']}", ".nf", roff(parser.format_help().split("\n\n", 1)[1].rstrip()), ".fi",
             f".SH {h['commands']}"]
    for name, sub in commands(parser).items():
        lines += [f".SS {name}", ".nf", roff(sub.format_help().rstrip()), ".fi"]
    lines += [f".SH {h['files']}", roff(h["files_text"]), f".SH {h['see']}", roff(h["window"]),
              f".SH {h['author']}", "Nicolas Vaughan <https://nicolasvaughan.org>"]
    return "\n".join(lines) + "\n"


def targets() -> dict[str, Path]:
    return {"en": MAN / "py-foliation.1", "es": MAN / "es" / "py-foliation.1"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make the manual pages from the help of the command line.")
    parser.add_argument("--check", action="store_true", help="only say whether they are up to date")
    args = parser.parse_args(argv)
    stale = []
    for lang, path in targets().items():
        text = page(lang)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"Wrote {path.relative_to(ROOT)}")
    if stale:
        sys.exit("Out of date (run uv run python tools/manpage.py): " + ", ".join(str(p.relative_to(ROOT))
                                                                          for p in stale))


if __name__ == "__main__":
    main()
