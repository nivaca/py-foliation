"""Page labels: the numbering a PDF viewer shows for each page.

A PDF keeps its page labels in the ``/PageLabels`` number tree of its
catalog. Each entry starts a *range* at a page (0-based in the file) and
gives its numbering style (``/S``), a prefix (``/P``) and the number of
its first page (``/St``, 1 if absent). A range lasts until the next one
starts. The styles are:

    D   1, 2, 3 ...             (decimal arabic numerals)
    r   i, ii, iii ...          (lowercase roman numerals)
    R   I, II, III ...          (uppercase roman numerals)
    a   a, b ... z, aa, bb ...  (lowercase letters)
    A   A, B ... Z, AA, BB ...  (uppercase letters)
    -   no number: the prefix only (no /S in the file)

Here pages are 1-based, as users write them. A range is written on the
command line in one of two ways:

    compact:  PAGES:STYLE[:START[:PREFIX]]     9:D   215:D:1:App-
    named:    PAGES [style=S] [start=N] [prefix=P]

PAGES is a first page (``9``) or a span (``9-200``, ``9..200``, ``201-``);
``LAST`` and ``LAST-N`` name pages from the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pikepdf
from pikepdf import Array, Dictionary, Name, Pdf

from .interface import N_, tr

STYLES = ["D", "r", "R", "a", "A", ""]  # (the file's codes; "" is no number)

# the names a style may be given by, besides its code
STYLE_NAMES = {
    "D": "arabic", "r": "roman", "R": "ROMAN", "a": "letters", "A": "LETTERS", "": "none",
}
NONE_CODE = "-"  # how "no number" is written in compact ranges

# how the styles are shown (with tr)
STYLE_TITLES = {
    "D": N_("1, 2, 3"), "r": N_("i, ii, iii"), "R": N_("I, II, III"),
    "a": N_("a, b, c"), "A": N_("A, B, C"), "": N_("no number (prefix only)"),
}

KEYS = ("style", "start", "prefix")  # of named ranges


class LabelError(Exception):
    """A user-facing error: a range that cannot be read, a page out of the document..."""


# =========================================================================== ranges


@dataclass(frozen=True)
class Range:
    """Pages from PAGE (1-based) on, numbered in STYLE from START, after PREFIX."""

    page: int
    style: str = "D"
    prefix: str = ""
    start: int = 1

    def label(self, page: int) -> str:
        """The label of PAGE (1-based, in this range)."""
        if not self.style:
            return self.prefix
        return self.prefix + format_number(self.start + page - self.page, self.style)

    def spec(self) -> str:
        """This range in the compact form (PAGE:STYLE[:START[:PREFIX]])."""
        out = f"{self.page}:{self.style or NONE_CODE}"
        if self.start != 1 or self.prefix:
            out += f":{self.start}"
        if self.prefix:
            out += f":{self.prefix}"
        return out


def style_code(name: str) -> str:
    """The code of a style given by its code (D, r...), its name (arabic, roman...) or '-'."""
    if name in ("D", "r", "R", "a", "A"):
        return name
    for code, long in STYLE_NAMES.items():
        if name == long:
            return code
    if name in (NONE_CODE, "") or name.lower() == "none":
        return ""
    if name.lower() == "arabic":
        return "D"
    raise LabelError(tr("unknown style {style!r} (one of: {styles})", style=name, styles=styles_help()))


def styles_help() -> str:
    return ", ".join(f"{c or NONE_CODE} ({STYLE_NAMES[c]})" for c in STYLES)


# =========================================================================== numbers


def to_roman(n: int) -> str:
    """N in uppercase roman numerals (thousands beyond 3999 as more Ms)."""
    out = []
    for value, digits in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        count, n = divmod(n, value)
        out.append(digits * count)
    return "".join(out)


def to_letters(n: int) -> str:
    """N as the PDF numbers pages with letters: A ... Z, AA ... ZZ, AAA ..."""
    return chr(ord("A") + (n - 1) % 26) * ((n - 1) // 26 + 1)


def format_number(n: int, style: str) -> str:
    if style == "D":
        return str(n)
    if style in ("r", "R"):
        s = to_roman(n)
        return s.lower() if style == "r" else s
    if style in ("a", "A"):
        s = to_letters(n)
        return s.lower() if style == "a" else s
    return ""


# =========================================================================== pages


_PAGE = re.compile(r"^(LAST)?(?:-?(\d+))?$")


def page_number(token: str, n: int) -> int:
    """A page number (1-based, LAST and LAST-N allowed) checked against N pages."""
    t = token.strip().upper()
    if t.isdigit():
        page = int(t)
    elif t == "LAST":
        page = n
    elif re.fullmatch(r"LAST-\d+", t):
        page = n - int(t[5:])
    else:
        raise LabelError(tr("invalid page number {token!r}", token=token))
    if not 1 <= page <= n:
        raise LabelError(tr("page {page} is not in the document (1-{count})", page=token.strip(), count=n))
    return page


def parse_pages(spec: str, n: int) -> tuple[int, int | None]:
    """(first, last) of PAGES: 9 -> (9, None), 9-200 or 9..200 -> (9, 200), 201- -> (201, N)."""
    s = spec.strip()
    if ".." in s:
        a, b = s.split("..", 1)
    else:
        m = re.fullmatch(r"(\d+|LAST(?:-\d+)?)-(\d*|LAST(?:-\d+)?)", s, re.IGNORECASE)
        if m and not re.fullmatch(r"LAST-\d+", s, re.IGNORECASE):
            a, b = m.group(1), m.group(2)
        else:
            return page_number(s, n), None
    first = page_number(a, n)
    last = page_number(b, n) if b.strip() else n
    if last < first:
        raise LabelError(tr("the range {spec!r} ends before it starts", spec=spec))
    return first, last


@dataclass(frozen=True)
class Request:
    """A range asked for: a Range, and the last page it covers (None: up to the next range)."""

    range: Range
    last: int | None = None


def _start(value: str, spec: str) -> int:
    if not value.strip():
        return 1
    if not value.strip().isdigit() or int(value) < 1:
        raise LabelError(tr("the start number in {spec!r} must be a whole number from 1 on", spec=spec))
    return int(value)


def parse_compact(spec: str, n: int) -> Request:
    """PAGES:STYLE[:START[:PREFIX]] (the prefix may hold colons)."""
    parts = spec.split(":", 3)
    if len(parts) < 2:
        raise LabelError(tr("a range is PAGES:STYLE[:START[:PREFIX]], as 9:D or 215:D:1:App- (not {spec!r})",
                            spec=spec))
    first, last = parse_pages(parts[0], n)
    style = style_code(parts[1])
    start = _start(parts[2] if len(parts) > 2 else "", spec)
    prefix = parts[3] if len(parts) > 3 else ""
    return Request(Range(first, style, prefix, start), last)


def parse_named(tokens: list[str], n: int) -> Request:
    """PAGES [style=S] [start=N] [prefix=P]."""
    if not tokens:
        raise LabelError(tr("--range needs the pages, as --range 9-200 style=arabic"))
    first, last = parse_pages(tokens[0], n)
    values = {"style": "D", "start": "1", "prefix": ""}
    for tok in tokens[1:]:
        key, eq, value = tok.partition("=")
        if not eq or key not in KEYS:
            raise LabelError(tr("{token!r} is not one of style=, start= or prefix=", token=tok))
        values[key] = value
    spec = " ".join(tokens)
    return Request(Range(first, style_code(values["style"]), values["prefix"], _start(values["start"], spec)), last)


# =========================================================================== reading and writing


def _entries(node, seen: set) -> list[tuple[int, Dictionary]]:
    """The (index, label dictionary) pairs of a number tree node and its kids."""
    if not isinstance(node, Dictionary) or node.objgen in seen and node.objgen != (0, 0):
        return []
    seen.add(node.objgen)
    out = []
    nums = node.get("/Nums")
    if isinstance(nums, Array):
        for i in range(0, len(nums) - 1, 2):
            key, value = nums[i], nums[i + 1]
            if isinstance(value, Dictionary):
                try:
                    out.append((int(key), value))
                except (TypeError, ValueError):
                    pass
    for kid in node.get("/Kids", []):
        out += _entries(kid, seen)
    return out


def read_labels(pdf: Pdf) -> list[Range]:
    """The ranges of the document's page labels ([] if it has none)."""
    tree = pdf.Root.get("/PageLabels")
    n = len(pdf.pages)
    ranges: dict[int, Range] = {}
    for index, d in _entries(tree, set()):
        if not 0 <= index < n:
            continue
        s = d.get("/S")
        style = str(s)[1:] if isinstance(s, Name) and str(s)[1:] in STYLES else ""
        prefix = str(d.get("/P", ""))
        try:
            start = max(int(d.get("/St", 1)), 1)
        except (TypeError, ValueError):
            start = 1
        ranges[index + 1] = Range(index + 1, style, prefix, start)
    return normalize(list(ranges.values()))


def write_labels(pdf: Pdf, ranges: list[Range]) -> None:
    """Give the document these ranges ([]: no page labels at all)."""
    ranges = normalize(ranges)
    if not ranges:
        if "/PageLabels" in pdf.Root:
            del pdf.Root["/PageLabels"]
        return
    nums = Array()
    for r in ranges:
        d = Dictionary(Type=Name.PageLabel)
        if r.style:
            d.S = Name("/" + r.style)
        if r.prefix:
            d.P = pikepdf.String(r.prefix)
        if r.start != 1:
            d.St = r.start
        nums.append(r.page - 1)
        nums.append(pdf.make_indirect(d))
    pdf.Root.PageLabels = pdf.make_indirect(Dictionary(Nums=nums))


# =========================================================================== computing


def normalize(ranges: list[Range]) -> list[Range]:
    """RANGES sorted by page, one per page (the last given wins), starting at page 1."""
    by_page: dict[int, Range] = {}
    for r in ranges:
        by_page[r.page] = r
    out = [by_page[p] for p in sorted(by_page)]
    if out and out[0].page != 1:
        out.insert(0, Range(1))
    return out


def page_labels(ranges: list[Range], n: int) -> list[str]:
    """The label of each of N pages (their numbers if there are no ranges)."""
    ranges = normalize(ranges)
    if not ranges:
        return [str(i + 1) for i in range(n)]
    out = []
    k = 0
    for page in range(1, n + 1):
        while k + 1 < len(ranges) and ranges[k + 1].page <= page:
            k += 1
        out.append(ranges[k].label(page))
    return out


def spans(ranges: list[Range], n: int) -> list[tuple[Range, int]]:
    """Each range of a document of N pages with its last page."""
    ranges = [r for r in normalize(ranges) if r.page <= n]
    return [(r, (ranges[i + 1].page - 1) if i + 1 < len(ranges) else n) for i, r in enumerate(ranges)]


def _page_specs(ranges: list[Range], n: int) -> list[tuple[str, str, int]]:
    """(style, prefix, number) of each page."""
    out = []
    ranges = normalize(ranges) or [Range(1)]
    for r, last in spans(ranges, n):
        for page in range(r.page, last + 1):
            out.append((r.style, r.prefix, r.start + page - r.page))
    return out


def _compress(specs: list[tuple[str, str, int]]) -> list[Range]:
    """The fewest ranges giving these (style, prefix, number) pages."""
    out: list[Range] = []
    prev = None
    for i, (style, prefix, number) in enumerate(specs):
        continues = (prev is not None and prev[0] == style and prev[1] == prefix
                     and (not style or number == prev[2] + 1))
        if not continues:
            out.append(Range(i + 1, style, prefix, number if style else 1))
        prev = (style, prefix, number)
    return out


def apply(base: list[Range], requests: list[Request], n: int, remove: list[int] = ()) -> list[Range]:
    """BASE (the ranges kept) with the REQUESTS laid over it, in a document of N pages.

    A request without a last page lasts until the next range starts (in BASE,
    or another request without a last page). Requests with a last page are
    laid over those: after one, the pages go on with the numbers they had.
    REMOVE: first pages whose range is dropped from BASE first (the range
    before it goes on over its pages).
    """
    base = normalize(base)
    for page in remove:
        if page == 1 or page not in {r.page for r in base}:
            raise LabelError(tr("no range starts at page {page} (ranges start at: {pages})", page=page,
                                pages=", ".join(str(r.page) for r in base[1:]) or "-"))
        base = [r for r in base if r.page != page]
    specs = _page_specs(base, n)
    open_ended = [q for q in requests if q.last is None]
    starts = {r.page for r in base} | {q.range.page for q in open_ended}
    for q in open_ended + [q for q in requests if q.last is not None]:
        r = q.range
        last = q.last
        if last is None:
            later = [p for p in starts if p > r.page]
            last = min(later) - 1 if later else n
        for page in range(r.page, last + 1):
            specs[page - 1] = (r.style, r.prefix, r.start + page - r.page)
    return _compress(specs)


def describe(r: Range, last: int) -> str:
    """'i … viii' (the labels of the first and last pages of a range)."""
    a, b = r.label(r.page), r.label(last)
    if last == r.page:
        return a
    if not r.style:
        return tr("{label} (every page)", label=a) if a else tr("(no label)")
    return f"{a} … {b}"
