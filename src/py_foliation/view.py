"""The view of a PDF when it is opened: how a viewer lays out its pages, at
what zoom, with which side panel, and at which page.

A PDF keeps these for the whole document (not for each page), in its catalog:

    /PageLayout   SinglePage, OneColumn (continuous), TwoPageLeft, TwoPageRight,
                  TwoColumnLeft, TwoColumnRight (two pages side by side; with
                  "Right", the first page is alone on the right, as in a book)
    /PageMode     UseNone, UseOutlines, UseThumbs, UseAttachments, UseOC,
                  FullScreen (what is shown beside the pages)
    /OpenAction   a destination: the page it opens at, and its zoom (/Fit,
                  /FitH, /FitV, /FitB, /FitBH, /FitBV, or /XYZ with a factor)

Whatever is not given is left to the viewer. Here a View holds the PDF's own
names; LAYOUTS, ZOOMS and PANELS give the names the command line uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal

from pikepdf import Array, Dictionary, Name, Pdf

from .interface import N_, tr
from .labels import LabelError, page_number

# PDF name -> name on the command line (and how the window shows it)
LAYOUTS = {
    "SinglePage": "single", "OneColumn": "continuous", "TwoPageLeft": "double",
    "TwoPageRight": "double-cover", "TwoColumnLeft": "double-continuous",
    "TwoColumnRight": "double-continuous-cover",
}
LAYOUT_TITLES = {
    "SinglePage": N_("One page at a time"), "OneColumn": N_("Continuous"),
    "TwoPageLeft": N_("Two pages at a time"),
    "TwoPageRight": N_("Two pages at a time, the first one alone (as a book)"),
    "TwoColumnLeft": N_("Two pages side by side, continuous"),
    "TwoColumnRight": N_("Two pages side by side, continuous, the first one alone (as a book)"),
}
ZOOMS = {
    "Fit": "fit-page", "FitH": "fit-width", "FitV": "fit-height", "FitB": "fit-visible",
    "FitBH": "fit-visible-width", "FitBV": "fit-visible-height",
}
ZOOM_TITLES = {
    "Fit": N_("Fit the page"), "FitH": N_("Fit the width"), "FitV": N_("Fit the height"),
    "FitB": N_("Fit what is printed"), "FitBH": N_("Fit the width of what is printed"),
    "FitBV": N_("Fit the height of what is printed"),
}
PANELS = {
    "UseNone": "none", "UseOutlines": "bookmarks", "UseThumbs": "thumbnails",
    "UseAttachments": "attachments", "UseOC": "layers", "FullScreen": "full-screen",
}
PANEL_TITLES = {
    "UseNone": N_("No panel"), "UseOutlines": N_("Bookmarks"), "UseThumbs": N_("Thumbnails"),
    "UseAttachments": N_("Attachments"), "UseOC": N_("Layers"), "FullScreen": N_("Full screen"),
}
DEFAULT = "default"  # (on the command line: leave it to the viewer)


@dataclass(frozen=True)
class View:
    """LAYOUT and PANEL: PDF names ('' for the viewer's choice). ZOOM: a PDF name
    (Fit, FitH ...), a percentage ('150') or ''. PAGE: the page it opens at
    (1-based; None for the viewer's choice; a zoom needs a page: 1 if none)."""

    layout: str = ""
    zoom: str = ""
    panel: str = ""
    page: int | None = None

    def __post_init__(self):
        if self.zoom and self.page is None:
            object.__setattr__(self, "page", 1)

    def __bool__(self) -> bool:
        return self != View()

    def options(self) -> list[str]:
        """This view as options of 'py-foliation view'."""
        out = []
        if self.layout:
            out += ["--layout", LAYOUTS[self.layout]]
        if self.zoom:
            out += ["--zoom", zoom_name(self.zoom)]
        if self.panel:
            out += ["--panel", PANELS[self.panel]]
        if self.page is not None:
            out += ["--open-at", str(self.page)]
        return out


def zoom_name(zoom: str) -> str:
    return f"{zoom}%" if zoom.isdigit() else ZOOMS[zoom]


def describe(v: View) -> list[tuple[str, str]]:
    """(what, how) for each part of V, as the window and 'show' print them."""
    default = tr("(the viewer's choice)")
    return [
        (tr("Layout"), tr(LAYOUT_TITLES[v.layout]) if v.layout else default),
        (tr("Zoom"), (f"{v.zoom} %" if v.zoom.isdigit() else tr(ZOOM_TITLES[v.zoom])) if v.zoom else default),
        (tr("Panel"), tr(PANEL_TITLES[v.panel]) if v.panel else default),
        (tr("Opens at"), tr("page {page}", page=v.page) if v.page is not None else default),
    ]


# =========================================================================== the command line


def _code(value: str, names: dict[str, str], what: str) -> str:
    """The PDF name of VALUE, given by its name on the command line ('default': '')."""
    v = value.strip().lower()
    if v == DEFAULT:
        return ""
    for code, name in names.items():
        if v in (name, code.lower()):
            return code
    raise LabelError(tr("unknown {what} {value!r} (one of: {names})", what=tr(what), value=value,
                        names=", ".join(list(names.values()) + [DEFAULT])))


def parse_layout(value: str) -> str:
    return _code(value, LAYOUTS, N_("layout"))


def parse_panel(value: str) -> str:
    return _code(value, PANELS, N_("panel"))


def parse_zoom(value: str) -> str:
    """A zoom: a name (fit-width ...), a percentage (150 or 150%) or 'default'."""
    m = re.fullmatch(r"\s*(\d+)\s*%?\s*", value)
    if m:
        if not 1 <= int(m[1]) <= 6400:
            raise LabelError(tr("the zoom must be from 1% to 6400% (not {value})", value=value))
        return str(int(m[1]))
    return _code(value, ZOOMS, N_("zoom"))


def parse_page(value: str, n: int) -> int | None:
    """The page to open at (1-based; LAST and LAST-N allowed), or None for 'default' (but
    with a zoom, a view opens at page 1)."""
    return None if value.strip().lower() == DEFAULT else page_number(value, n)


def changed(v: View, n: int, layout: str | None = None, zoom: str | None = None, panel: str | None = None,
            page: str | None = None) -> View:
    """V with the parts given on the command line (None: kept) changed, in a document of N pages."""
    changes = {}
    if layout is not None:
        changes["layout"] = parse_layout(layout)
    if panel is not None:
        changes["panel"] = parse_panel(panel)
    if zoom is not None:
        changes["zoom"] = parse_zoom(zoom)
    if page is not None:
        changes["page"] = parse_page(page, n)
    new = replace(v, **changes)
    if page is None and zoom is not None and not new.zoom and v.page == 1:
        new = replace(new, page=None)  # (the page was only there for the zoom)
    return new


# =========================================================================== reading and writing


def _name(value) -> str:
    return str(value)[1:] if isinstance(value, Name) else ""


def _destination(pdf: Pdf, action) -> tuple[int | None, str] | None:
    """(page, zoom) of an /OpenAction that goes to a page of this document; None if it is something else."""
    if isinstance(action, Dictionary) and _name(action.get("/S")) == "GoTo":
        action = action.get("/D")
    if not isinstance(action, Array) or len(action) < 2:
        return None
    target = action[0]
    if isinstance(target, Dictionary):
        pages = {p.obj.objgen: i for i, p in enumerate(pdf.pages)}
        index = pages.get(target.objgen)
    else:
        try:
            index = int(target)
        except (TypeError, ValueError):
            return None
    if index is None or not 0 <= index < len(pdf.pages):
        return None
    kind = _name(action[1])
    if kind in ZOOMS:
        return index + 1, kind
    if kind == "XYZ":
        factor = action[4] if len(action) > 4 else None
        try:
            percent = round(float(factor) * 100) if factor is not None else 0
        except (TypeError, ValueError):
            percent = 0
        return index + 1, str(percent) if percent > 0 else ""
    return None


def read_view(pdf: Pdf) -> View:
    """The view of the document when it is opened (the parts it doesn't give, or that
    py-foliation doesn't know, are left empty)."""
    root = pdf.Root
    layout = _name(root.get("/PageLayout"))
    panel = _name(root.get("/PageMode"))
    dest = _destination(pdf, root.get("/OpenAction"))
    page, zoom = dest if dest else (None, "")
    return View(layout if layout in LAYOUTS else "", zoom, panel if panel in PANELS else "", page)


def write_view(pdf: Pdf, v: View) -> None:
    """Give the document the view V, changing only the parts it doesn't have yet
    (so that what py-foliation doesn't know is kept, unless it is replaced)."""
    old = read_view(pdf)
    root = pdf.Root
    for key, value, before in (("/PageLayout", v.layout, old.layout), ("/PageMode", v.panel, old.panel)):
        if value != before:
            if value:
                root[key] = Name("/" + value)
            elif key in root:
                del root[key]
    if (v.page, v.zoom) != (old.page, old.zoom):
        if v.page is None:
            if "/OpenAction" in root:
                del root["/OpenAction"]
            return
        page = pdf.pages[min(v.page, len(pdf.pages)) - 1].obj
        if not v.zoom:
            dest = [page, Name.XYZ, None, None, None]  # (the viewer's zoom)
        elif v.zoom.isdigit():
            dest = [page, Name.XYZ, None, None, Decimal(v.zoom) / 100]
        elif v.zoom in ("Fit", "FitB"):
            dest = [page, Name("/" + v.zoom)]
        else:
            dest = [page, Name("/" + v.zoom), None]
        root.OpenAction = Array(dest)
