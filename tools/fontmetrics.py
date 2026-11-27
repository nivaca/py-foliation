#!/usr/bin/env python3
"""Hace src/py_foliation/fontmetrics.py: los anchos de los caracteres de las doce
fuentes estándar de PDF que usan los encabezados y pies de página (Helvetica, Times y
Courier, cada una en redonda, negrita, cursiva y negrita cursiva), en WinAnsiEncoding.

Los anchos se leen de los archivos AFM de las fuentes URW base 35, que tienen las mismas
métricas que las de Adobe (en Fedora, urw-base35-fonts), y los nombres de los glifos se
convierten en caracteres con la Adobe Glyph List de fontTools:

    uv run --with fonttools python tools/fontmetrics.py [AFM_FOLDER]
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.agl import toUnicode

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "py_foliation" / "fontmetrics.py"

# PDF base font -> URW AFM file
FONTS = {
    "Helvetica": "NimbusSans-Regular", "Helvetica-Bold": "NimbusSans-Bold",
    "Helvetica-Oblique": "NimbusSans-Italic", "Helvetica-BoldOblique": "NimbusSans-BoldItalic",
    "Times-Roman": "NimbusRoman-Regular", "Times-Bold": "NimbusRoman-Bold",
    "Times-Italic": "NimbusRoman-Italic", "Times-BoldItalic": "NimbusRoman-BoldItalic",
    "Courier": "NimbusMonoPS-Regular", "Courier-Bold": "NimbusMonoPS-Bold",
    "Courier-Oblique": "NimbusMonoPS-Italic", "Courier-BoldOblique": "NimbusMonoPS-BoldItalic",
}

# ascender and descender of each family, from Adobe's AFM files (the URW files give 0)
VERTICAL = {"Helvetica": (718, -207), "Times": (683, -217), "Courier": (629, -157)}


def read_afm(path: Path) -> tuple[dict[str, int], int, int]:
    """{character: width}, ascender and descender of an AFM file (in 1/1000 of the size)."""
    widths: dict[str, int] = {}
    ascender = descender = 0
    for line in path.read_text(encoding="latin-1").splitlines():
        if line.startswith("Ascender "):
            ascender = round(float(line.split()[1]))
        elif line.startswith("Descender "):
            descender = round(float(line.split()[1]))
        elif line.startswith("C "):
            fields = dict(f.strip().split(" ", 1) for f in line.split(";") if f.strip())
            char = toUnicode(fields["N"])
            if len(char) == 1:
                widths.setdefault(char, round(float(fields["WX"])))
    return widths, ascender, descender


def main(argv: list[str]) -> int:
    folder = Path(argv[0]) if argv else Path("/usr/share/fonts/urw-base35")
    # every character WinAnsiEncoding (cp1252) can write
    chars = sorted({c for b in range(32, 256) for c in bytes([b]).decode("cp1252", errors="ignore")
                    if c.isprintable() or c == "\xa0"})
    lines = [
        '"""The widths of the characters of the standard PDF fonts, in 1/1000 of the font size,',
        "for the characters WinAnsiEncoding (cp1252) can write; made by tools/fontmetrics.py",
        'from the URW base 35 fonts, whose metrics are those of the Adobe fonts. Do not edit."""',
        "",
        "# base font: (ascender, descender, {character: width})",
        "FONTS = {",
    ]
    for base, urw in FONTS.items():
        widths, ascender, descender = read_afm(folder / f"{urw}.afm")
        if not (ascender and descender):
            ascender, descender = VERTICAL[base.split("-")[0]]
        missing = [c for c in chars if c not in widths]
        if missing:
            print(f"fontmetrics.py: {urw} lacks {missing!r}", file=sys.stderr)
        table = {c: widths[c] for c in chars if c in widths}
        lines.append(f"    {base!r}: ({ascender}, {descender}, {{")
        items = [f"{c!r}: {w}" for c, w in table.items()]
        row = "       "
        for item in items:
            if len(row) + len(item) + 2 > 116:
                lines.append(row.rstrip())
                row = "       "
            row += f" {item},"
        lines.append(row.rstrip())
        lines.append("    }),")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
