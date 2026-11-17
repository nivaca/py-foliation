"""Headers and footers: text drawn on the pages, above and below their content.

Unlike the page labels and the view, these change the pages themselves. A
header and a footer have three places each, left, center and right, whose
text may hold variables ($page, $pagelabel, $totalpages, $date ...: see
VARIABLES), and are drawn in one of the PDF standard fonts (Helvetica, Times
or Courier), which every viewer has. Those fonts write the characters of
WinAnsiEncoding (cp1252): Latin script, with its accents and signs, but not
Greek or Cyrillic.

On each page they are drawn in a content stream of their own, after the
original content, which is wrapped in q ... Q so that nothing it leaves set
changes them; with "shrink", the original content is also scaled down to
leave room for them. A record in the page dictionary names what was added
and changed (PRIVATE), so that remove() can put the page back as it was,
and so that applying a header and footer again replaces the old one.

Margins are the distances from the edges of the page (as it is shown, after
/Rotate) to the outer edge of the header and footer: the top margin to the
top of the header, the bottom margin to the bottom of the footer, and the
left and right margins to the text at the sides.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name, Pdf

from . import config
from .fontmetrics import FONTS
from .interface import N_, tr
from .labels import LabelError, page_labels, parse_pages, read_labels

PRIVATE = "/PyFoliationHeaderFooter"  # the record of a page with a header or footer added
POINTS = {"in": 72.0, "cm": 72 / 2.54, "pt": 1.0}  # points in each unit
FAMILIES = {"helvetica": "Helvetica", "times": "Times", "courier": "Courier"}
FAMILY_TITLES = {"helvetica": "Helvetica", "times": "Times", "courier": "Courier"}
SIDES = {"top": N_("top"), "bottom": N_("bottom"), "left": N_("left"), "right": N_("right")}  # (the margins)
UNIT_TITLES = {"in": N_("inches"), "cm": N_("centimeters"), "pt": N_("points")}
PARITIES = {"all": N_("All pages"), "even": N_("Even pages only"), "odd": N_("Odd pages only")}
SLOTS = ("header_left", "header_center", "header_right", "footer_left", "footer_center", "footer_right")
SLOT_TITLES = {
    "header_left": N_("Header left"), "header_center": N_("Header center"), "header_right": N_("Header right"),
    "footer_left": N_("Footer left"), "footer_center": N_("Footer center"), "footer_right": N_("Footer right"),
}
LINE = 1.2  # the distance between lines, in font sizes
PAD = 0.3  # the room around the text inside a border or a background, in font sizes

# $name -> what it writes (for the help of the window and the command line)
VARIABLES = {
    "page": N_("the page number (of the file, from 1)"),
    "pagelabel": N_("the label of the page"),
    "bookmark": N_("the bookmark the page is under"),
    "totalpages": N_("the number of pages of the document"),
    "author": N_("the author of the document (as its properties give it)"),
    "filename": N_("the name of the file"),
    "filepath": N_("the full path of the file"),
    "date": N_("today's date, as Nov 28, 2007"),
    "shortdate": N_("today's date, as 11/28/07"),
    "time": N_("the time, as 3:05 PM"),
    "day": N_("the day of the month"),
    "month": N_("the month, in two digits"),
    "year": N_("the year, in four digits"),
    "shortyear": N_("the year, in two digits"),
    "hour": N_("the hour, from 1 to 12"),
    "longhour": N_("the hour, from 0 to 23"),
    "minute": N_("the minute"),
    "second": N_("the second"),
    "ampm": N_("AM or PM"),
    "bates": N_("the Bates number: the prefix, the number and the suffix (see Bates numbering)"),
}
MONTHS = (N_("Jan"), N_("Feb"), N_("Mar"), N_("Apr"), N_("May"), N_("Jun"), N_("Jul"), N_("Aug"), N_("Sep"),
          N_("Oct"), N_("Nov"), N_("Dec"))
_VARIABLE = re.compile(r"\$\$|\$(" + "|".join(sorted(VARIABLES, key=len, reverse=True)) + ")")


@dataclass(frozen=True)
class HeaderFooter:
    """What to draw, where, how and on which pages (and, as a profile, under what name)."""

    header_left: str = ""
    header_center: str = ""
    header_right: str = ""
    footer_left: str = ""
    footer_center: str = ""
    footer_right: str = ""
    # margins, in UNITS (in, cm or pt)
    units: str = "cm"
    top: float = 1.0
    bottom: float = 1.0
    left: float = 2.0
    right: float = 2.0
    shrink: bool = False  # scale the content of the pages down, to leave room for the header and footer
    # appearance
    font: str = "helvetica"  # helvetica, times or courier
    size: float = 10.0
    color: str = "#000000"
    bold: bool = False
    italic: bool = False
    border: bool = False
    border_color: str = "#000000"
    border_width: float = 0.5  # points
    background: str = ""  # a color, or "" for none
    # pages: a list of pages ("" for all; "5-200", "1,3,9-"), and of those, all, the even or the odd ones
    pages: str = ""
    parity: str = "all"
    # Bates numbering ($bates): PREFIX, the number from START in DIGITS digits (at least), SUFFIX
    bates_prefix: str = ""
    bates_start: int = 1
    bates_digits: int = 6
    bates_suffix: str = ""
    # as a profile
    name: str = ""
    show_on_menu: bool = False

    def texts(self) -> dict[str, str]:
        return {slot: getattr(self, slot) for slot in SLOTS}

    def has_text(self) -> bool:
        return any(t.strip() for t in self.texts().values())

    def base_font(self) -> str:
        family = FAMILIES[self.font]
        style = {(False, False): "", (True, False): "Bold", (False, True): "Oblique", (True, True): "BoldOblique"}
        name = style[self.bold, self.italic]
        if family == "Times":
            name = {"": "Roman", "Oblique": "Italic", "BoldOblique": "BoldItalic"}.get(name, name)
        return f"{family}-{name}" if name else family

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> HeaderFooter:
        """A HeaderFooter from a dictionary (of a profile), leaving out what it doesn't know."""
        known = {f.name: f for f in fields(cls)}
        values = {}
        for key, value in data.items():
            if key in known:
                kind = type(getattr(cls(), key))
                try:
                    values[key] = kind(value)
                except (TypeError, ValueError):
                    continue
        return check(cls(**values))


def _color(value: str, what: str) -> tuple[float, float, float]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if not m:
        raise LabelError(tr("the {what} must be a color as #RRGGBB (not {value!r})", what=tr(what), value=value))
    h = m[1]
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def check(hf: HeaderFooter) -> HeaderFooter:
    """HF if its settings are right (raises LabelError if not), with its colors written as #rrggbb."""
    if hf.units not in POINTS:
        raise LabelError(tr("the units must be in, cm or pt (not {value!r})", value=hf.units))
    if hf.font not in FAMILIES:
        raise LabelError(tr("the font must be helvetica, times or courier (not {value!r})", value=hf.font))
    if hf.parity not in PARITIES:
        raise LabelError(tr("the pages must be all, even or odd (not {value!r})", value=hf.parity))
    if not 1 <= hf.size <= 200:
        raise LabelError(tr("the font size must be from 1 to 200 points (not {value})", value=hf.size))
    for side, what in SIDES.items():
        if getattr(hf, side) < 0:
            raise LabelError(tr("the {what} margin cannot be negative", what=tr(what)))
    if not 0 <= hf.border_width <= 20:
        raise LabelError(tr("the width of the border must be from 0 to 20 points"))
    if hf.bates_start < 0 or not 1 <= hf.bates_digits <= 20:
        raise LabelError(tr("the Bates number starts at 0 or more, with 1 to 20 digits"))
    colors = {"color": _color(hf.color, N_("color")), "border_color": _color(hf.border_color, N_("border color"))}
    if hf.background:
        colors["background"] = _color(hf.background, N_("background color"))
    return replace(hf, **{k: "#%02x%02x%02x" % tuple(round(c * 255) for c in v) for k, v in colors.items()})


# =========================================================================== the pages


def chosen_pages(hf: HeaderFooter, n: int) -> list[int]:
    """The pages (1-based) of a document of N pages that HF goes on."""
    if hf.pages.strip():
        pages: set[int] = set()
        for part in hf.pages.split(","):
            if part.strip():
                first, last = parse_pages(part, n)
                pages.update(range(first, (last or first) + 1))
    else:
        pages = set(range(1, n + 1))
    if hf.parity == "even":
        pages = {p for p in pages if p % 2 == 0}
    elif hf.parity == "odd":
        pages = {p for p in pages if p % 2 == 1}
    return sorted(pages)


def compact_pages(pages) -> str:
    """'3-5,9': PAGES (1-based) as a list of pages."""
    out, run = [], []
    for p in sorted(set(pages)):
        if run and p == run[-1] + 1:
            run.append(p)
            continue
        if run:
            out.append(f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0]))
        run = [p]
    if run:
        out.append(f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0]))
    return ",".join(out)


# =========================================================================== the variables


@dataclass(frozen=True)
class Document:
    """What the variables of a document need to know of it."""

    count: int
    labels: tuple[str, ...]
    bookmarks: tuple[str, ...]  # the bookmark each page is under ("" if none)
    author: str = ""
    path: Path | None = None


def bookmarks_of(pdf: Pdf) -> tuple[str, ...]:
    """The title of the bookmark (outline item) each page is under: the last one, in the
    order of the outline, that goes to it or to a page before it ('' if none)."""
    from .view import _destination  # (an explicit destination: its page)

    n = len(pdf.pages)
    starts: list[tuple[int, int, str]] = []  # (page, order, title)
    names = {}
    try:
        if "/Dests" in pdf.Root:
            names.update({str(k): v for k, v in pdf.Root.Dests.items()})
        if "/Names" in pdf.Root and "/Dests" in pdf.Root.Names:
            names.update({str(k): v for k, v in pikepdf.NameTree(pdf.Root.Names.Dests).items()})
    except (pikepdf.PdfError, TypeError, ValueError, KeyError):
        pass
    try:
        with pdf.open_outline() as outline:
            order = 0

            def walk(items):
                nonlocal order
                for item in items:
                    target = item.destination
                    if target is None and item.action is not None and item.action.get("/S") == Name.GoTo:
                        target = item.action.get("/D")
                    if isinstance(target, (pikepdf.String, Name)) or isinstance(target, str):
                        target = names.get(str(target).lstrip("/"), names.get(str(target)))
                    if isinstance(target, Dictionary):
                        target = target.get("/D")
                    found = _destination(pdf, target) if target is not None else None
                    if found:
                        starts.append((found[0], order, str(item.title or "")))
                    order += 1
                    walk(item.children)

            walk(outline.root)
    except (pikepdf.PdfError, pikepdf.OutlineStructureError, TypeError, ValueError, KeyError):
        return ("",) * n
    starts.sort()
    out, k, current = [], 0, ""
    for page in range(1, n + 1):
        while k < len(starts) and starts[k][0] <= page:
            current = starts[k][2]
            k += 1
        out.append(current)
    return tuple(out)


def document_of(pdf: Pdf, path: Path | None = None, labels: list[str] | None = None) -> Document:
    """What the variables need of PDF (with these LABELS of its pages, or those it has)."""
    n = len(pdf.pages)
    if labels is None:
        labels = page_labels(read_labels(pdf), n)
    author = ""
    try:
        author = str(pdf.docinfo.get("/Author", "")) if pdf.trailer.get("/Info") is not None else ""
    except (pikepdf.PdfError, ValueError):
        pass
    return Document(n, tuple(labels), bookmarks_of(pdf), author, path)


def expand(text: str, page: int, doc: Document, now: datetime, bates: str = "") -> str:
    """TEXT with its variables replaced, on PAGE (1-based) of DOC ($$ writes $)."""
    hour12 = now.hour % 12 or 12
    values = {
        "page": str(page),
        "pagelabel": doc.labels[page - 1] if page <= len(doc.labels) else str(page),
        "bookmark": doc.bookmarks[page - 1] if page <= len(doc.bookmarks) else "",
        "totalpages": str(doc.count),
        "author": doc.author,
        "filename": doc.path.name if doc.path else "",
        "filepath": str(doc.path.resolve()) if doc.path else "",
        "day": str(now.day),
        "month": f"{now.month:02d}",
        "year": f"{now.year:04d}",
        "shortyear": f"{now.year % 100:02d}",
        "hour": str(hour12),
        "longhour": f"{now.hour:02d}",
        "minute": f"{now.minute:02d}",
        "second": f"{now.second:02d}",
        "ampm": "AM" if now.hour < 12 else "PM",
        "bates": bates,
    }
    values["date"] = tr("{month} {day}, {year}", month=tr(MONTHS[now.month - 1]), day=now.day, year=now.year)
    values["shortdate"] = tr("{month}/{day}/{year}", month=values["month"], day=f"{now.day:02d}",
                             year=values["shortyear"])
    values["time"] = tr("{hour}:{minute} {ampm}", hour=hour12, minute=values["minute"], ampm=values["ampm"])
    return _VARIABLE.sub(lambda m: "$" if m[0] == "$$" else values[m[1]], text)


def bates_number(hf: HeaderFooter, index: int) -> str:
    return f"{hf.bates_prefix}{hf.bates_start + index:0{hf.bates_digits}d}{hf.bates_suffix}"


def unwritable(text: str) -> str:
    """The characters of TEXT the standard fonts cannot write ('' if none)."""
    widths = FONTS["Helvetica"][2]
    return "".join(sorted({c for c in text if c not in widths and c not in "\n\t"}))


def text_width(text: str, base_font: str, size: float) -> float:
    widths = FONTS[base_font][2]
    return sum(widths.get(c, 0) for c in text) * size / 1000


# =========================================================================== drawing


Matrix = tuple[float, float, float, float, float, float]


def _multiply(m: Matrix, n: Matrix) -> Matrix:
    """The matrix of doing M, then N (as PDF writes them: [a b c d e f])."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)


def _invert(m: Matrix) -> Matrix:
    a, b, c, d, e, f = m
    det = a * d - b * c
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(e * ia + f * ic), -(e * ib + f * id_))


def _apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def shown_frame(page: pikepdf.Page) -> tuple[float, float, Matrix]:
    """(width, height, matrix) of PAGE as it is shown: its crop box, turned by /Rotate. The
    matrix takes points of the page as shown (from its lower left corner) to its own space."""
    x0, y0, x1, y1 = (float(v) for v in page.cropbox)
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    w, h = x1 - x0, y1 - y0
    rotate = int(page.obj.get("/Rotate", 0) or 0) % 360
    if rotate == 90:
        return h, w, (0, 1, -1, 0, x1, y0)
    if rotate == 180:
        return w, h, (-1, 0, 0, -1, x1, y1)
    if rotate == 270:
        return h, w, (0, -1, 1, 0, x0, y1)
    return w, h, (1, 0, 0, 1, x0, y0)


def _number(x: float) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _pdf_string(text: str) -> bytes:
    data = text.encode("cp1252")
    return b"(" + data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


@dataclass(frozen=True)
class Block:
    """The lines of one place (header left ...) and where they go, on a page as it is shown."""

    slot: str
    lines: tuple[str, ...]
    x: float  # the left of the box (with its padding)
    y: float  # the bottom of the box
    width: float
    height: float


def _pad(hf: HeaderFooter) -> float:
    return PAD * hf.size if (hf.border or hf.background) else 0.0


def _box_height(hf: HeaderFooter, lines: int) -> float:
    asc, desc, _ = FONTS[hf.base_font()]
    return (asc - desc) / 1000 * hf.size + (lines - 1) * LINE * hf.size + 2 * _pad(hf)


def layout(hf: HeaderFooter, texts: dict[str, str], width: float, height: float) -> list[Block]:
    """Where the text of each place goes on a page of WIDTH x HEIGHT points, as it is shown."""
    font = hf.base_font()
    pad = _pad(hf)
    unit = POINTS[hf.units]
    top, bottom, left, right = hf.top * unit, hf.bottom * unit, hf.left * unit, hf.right * unit
    blocks = []
    for slot in SLOTS:
        text = texts.get(slot, "")
        if not text.strip():
            continue
        lines = tuple(text.split("\n"))
        box_w = max(text_width(line, font, hf.size) for line in lines) + 2 * pad
        box_h = _box_height(hf, len(lines))
        side = slot.split("_")[1]
        x = left if side == "left" else width - right - box_w if side == "right" else (width - box_w) / 2
        y = height - top - box_h if slot.startswith("header") else bottom
        blocks.append(Block(slot, lines, x, y, box_w, box_h))
    return blocks


def _rgb(color: str, operator: str) -> str:
    r, g, b = _color(color, N_("color"))
    return f"{_number(r)} {_number(g)} {_number(b)} {operator}"


def draw(hf: HeaderFooter, blocks: list[Block], font_name: str) -> bytes:
    """The content that draws BLOCKS, in the coordinates of the page as it is shown, with the
    font as the resource FONT_NAME; the header and the footer are marked as pagination artifacts."""
    font = hf.base_font()
    asc = FONTS[font][0]
    pad = _pad(hf)
    out: list[bytes] = []
    for kind, prefix in (("Header", "header_"), ("Footer", "footer_")):
        group = [b for b in blocks if b.slot.startswith(prefix)]
        if not group:
            continue
        out.append(f"/Artifact <</Type /Pagination /Subtype /{kind}>> BDC".encode())
        for b in group:
            rect = f"{_number(b.x)} {_number(b.y)} {_number(b.width)} {_number(b.height)} re"
            if hf.background:
                out.append(f"q {_rgb(hf.background, 'rg')} {rect} f Q".encode())
            if hf.border and hf.border_width > 0:
                out.append(f"q {_rgb(hf.border_color, 'RG')} {_number(hf.border_width)} w {rect} S Q".encode())
            side = b.slot.split("_")[1]
            inner = b.width - 2 * pad
            baseline = b.y + b.height - pad - asc / 1000 * hf.size
            for line in b.lines:
                if line:
                    free = inner - text_width(line, font, hf.size)
                    x = b.x + pad + (0 if side == "left" else free if side == "right" else free / 2)
                    out.append(f"BT /{font_name} {_number(hf.size)} Tf {_rgb(hf.color, 'rg')} "
                               f"{_number(x)} {_number(baseline)} Td ".encode() + _pdf_string(line) + b" Tj ET")
                baseline -= LINE * hf.size
        out.append(b"EMC")
    return b"\n".join(out)


def shrink_matrix(hf: HeaderFooter, width: float, height: float) -> Matrix:
    """The matrix that scales the content of a page of WIDTH x HEIGHT (as it is shown) down so
    that it fits between the header and the footer, centered across the page."""
    unit = POINTS[hf.units]
    header, footer = (_box_height(hf, n) if n else 0.0 for n in _lines_per_band(hf))
    gap = 0.5 * hf.size
    reserved_top = hf.top * unit + header + gap if header else 0.0
    reserved_bottom = hf.bottom * unit + footer + gap if footer else 0.0
    scale = (height - reserved_top - reserved_bottom) / height
    if scale < 0.2:
        raise LabelError(tr("the header and footer leave too little room to shrink the pages into"))
    return (scale, 0, 0, scale, (width - scale * width) / 2, reserved_bottom)


def _lines_per_band(hf: HeaderFooter) -> tuple[int, int]:
    """(header, footer): the most lines a place of each has (0 if none has text)."""
    out = []
    for prefix in ("header_", "footer_"):
        out.append(max((len(t.split("\n")) for s, t in hf.texts().items() if s.startswith(prefix) and t.strip()),
                       default=0))
    return out[0], out[1]


# =========================================================================== applying and removing


def _contents(page: pikepdf.Page) -> list:
    """The content streams of PAGE (its /Contents, one stream or an array of them)."""
    contents = page.obj.get("/Contents")
    if contents is None:
        return []
    return list(contents) if isinstance(contents, Array) else [contents]


def has_header_footer(page: pikepdf.Page) -> bool:
    return PRIVATE in page.obj


def remove_from_page(page: pikepdf.Page) -> bool:
    """Take away the header and footer py-foliation added to PAGE, and put its content back as
    it was (False if it had none)."""
    record = page.obj.get(PRIVATE)
    if record is None:
        return False
    added = {s.objgen for s in record.get("/Streams", Array())}
    contents = page.obj.get("/Contents")
    if isinstance(contents, Array):
        kept = [s for s in contents if s.objgen not in added]
        page.obj.Contents = kept[0] if len(kept) == 1 else Array(kept)
    # (the links and other annotations were moved with the content: back where they were)
    for annot, rect in zip(record.get("/Annots", Array()), record.get("/Rects", Array())):
        annot.Rect = Array(list(rect))
    font = record.get("/Font")
    resources = page.obj.get("/Resources")
    if font is not None and resources is not None and "/Font" in resources and font in resources.Font:
        del resources.Font[font]
    del page.obj[PRIVATE]
    return True


def _moved_rect(rect, m: Matrix) -> Array:
    x0, y0, x1, y1 = (float(v) for v in rect)
    corners = [_apply(m, x, y) for x in (x0, x1) for y in (y0, y1)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    return Array([min(xs), min(ys), max(xs), max(ys)])


def page_texts(hf: HeaderFooter, doc: Document, now: datetime) -> list[tuple[int, dict[str, str]]]:
    """(page, {place: text}) for each page HF goes on, with the variables replaced; raises
    LabelError if the standard fonts cannot write a text, or if there is no text at all."""
    if not hf.has_text():
        raise LabelError(tr("no text for the header or the footer"))
    out = []
    for index, number in enumerate(chosen_pages(hf, doc.count)):
        texts = {slot: expand(text, number, doc, now, bates_number(hf, index))
                 for slot, text in hf.texts().items()}
        bad = unwritable("".join(texts.values()))
        if bad:
            raise LabelError(tr("the standard PDF fonts cannot write {chars!r} (page {page})", chars=bad,
                                page=number))
        out.append((number, texts))
    return out


def _font(pdf: Pdf, hf: HeaderFooter) -> pikepdf.Object:
    return pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name("/" + hf.base_font()),
                                        Encoding=Name.WinAnsiEncoding))


def stamp_page(pdf: Pdf, page: pikepdf.Page, hf: HeaderFooter, texts: dict[str, str],
               font: pikepdf.Object | None = None) -> None:
    """Draw TEXTS ({place: text}, the variables already replaced) on PAGE of PDF as HF says,
    replacing the header and footer py-foliation added to it before."""
    remove_from_page(page)
    font = font if font is not None else _font(pdf, hf)
    width, height, frame = shown_frame(page)
    record = Dictionary()
    before = b"q"
    if hf.shrink and hf.has_text():
        shrink = _multiply(_multiply(_invert(frame), shrink_matrix(hf, width, height)), frame)
        before += (" " + " ".join(_number(v) for v in shrink) + " cm").encode()
        moved, rects = Array(), Array()
        for annot in page.obj.get("/Annots", Array()):
            if isinstance(annot, Dictionary) and "/Rect" in annot:
                rects.append(Array(list(annot.Rect)))
                annot.Rect = _moved_rect(annot.Rect, shrink)
                moved.append(annot)
        record.Annots, record.Rects = moved, rects
    font_name = page.add_resource(font, Name.Font, prefix="PyFol")
    blocks = layout(hf, texts, width, height)
    after = (b"Q\nq " + " ".join(_number(v) for v in frame).encode() + b" cm\n"
             + draw(hf, blocks, str(font_name)[1:]) + b"\nQ")
    before_stream = pdf.make_indirect(pikepdf.Stream(pdf, before))
    after_stream = pdf.make_indirect(pikepdf.Stream(pdf, after))
    page.obj.Contents = Array([before_stream, *_contents(page), after_stream])
    record.Streams = Array([before_stream, after_stream])
    record.Font = font_name
    page.obj[PRIVATE] = record


def apply(pdf: Pdf, hf: HeaderFooter, doc: Document, now: datetime | None = None) -> int:
    """Draw HF on its pages of PDF (replacing the header and footer py-foliation added to them
    before); DOC gives the variables what they need. The number of pages it went on."""
    hf = check(hf)
    pages = page_texts(hf, doc, now or datetime.now())
    font = _font(pdf, hf)
    for number, texts in pages:
        stamp_page(pdf, pdf.pages[number - 1], hf, texts, font)
    return len(pages)


def remove(pdf: Pdf, pages: str = "") -> int:
    """Take away the headers and footers py-foliation added to PAGES ('' for all); the number
    of pages it took them from."""
    chosen = chosen_pages(HeaderFooter(pages=pages), len(pdf.pages))
    return sum(remove_from_page(pdf.pages[p - 1]) for p in chosen)


def pages_with(pdf: Pdf) -> list[int]:
    """The pages (1-based) with a header or footer added by py-foliation."""
    return [i + 1 for i, page in enumerate(pdf.pages) if has_header_footer(page)]


# =========================================================================== changes waiting to be saved


@dataclass(frozen=True)
class Change:
    """A header and footer to add (HF), or those added to remove (on PAGES: '' for all)."""

    hf: HeaderFooter | None = None
    pages: str = ""

    def apply(self, pdf: Pdf, doc: Document, now: datetime | None = None) -> int:
        return apply(pdf, self.hf, doc, now) if self.hf is not None else remove(pdf, self.pages)


# =========================================================================== profiles


def profiles_path() -> Path:
    return config.config_dir() / "header-footer.json"


def read_profiles() -> dict[str, HeaderFooter]:
    """The saved profiles, by name ({} if none or if the file cannot be read)."""
    try:
        data = json.loads(profiles_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for item in data.get("profiles", []) if isinstance(data, dict) else []:
        if isinstance(item, dict) and item.get("name"):
            try:
                hf = HeaderFooter.from_dict(item)
            except LabelError:
                continue
            out[hf.name] = hf
    return out


def write_profiles(profiles: dict[str, HeaderFooter]) -> Path:
    """Keep PROFILES (raises OSError if they cannot be written)."""
    path = profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"profiles": [hf.as_dict() for hf in sorted(profiles.values(), key=lambda h: h.name.casefold())]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def save_profile(hf: HeaderFooter) -> Path:
    if not hf.name.strip():
        raise LabelError(tr("a profile needs a name"))
    profiles = read_profiles()
    profiles[hf.name] = check(hf)
    return write_profiles(profiles)


def delete_profile(name: str) -> bool:
    profiles = read_profiles()
    if name not in profiles:
        return False
    del profiles[name]
    write_profiles(profiles)
    return True
