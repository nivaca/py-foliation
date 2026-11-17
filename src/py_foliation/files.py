"""Reading and writing files: PDFs (keeping their protection) and lists of labels."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

import pikepdf
from pikepdf import Pdf

from . import headfoot, labels
from .interface import tr
from .labels import LabelError, Range
from .view import View, write_view


def open_pdf(path: Path, in_place: bool = False, password: str = "") -> Pdf:
    if not path.is_file():
        raise LabelError(tr("{path} not found", path=path))
    try:
        return Pdf.open(path, allow_overwriting_input=in_place, password=password)
    except pikepdf.PasswordError:
        raise LabelError(tr("{path} is protected by a password (give it with --password)", path=path)) from None
    except pikepdf.PdfError as e:
        raise LabelError(tr("{path} cannot be read as a PDF: {error}", path=path, error=e)) from None


def _save(pdf: Pdf, out: Path | str) -> None:
    """Save PDF as OUT, keeping its protection if it has one."""
    pdf.save(out, encryption=True if pdf.is_encrypted else None)


def save_pdf(pdf: Pdf, out: Path) -> None:
    """Save PDF as OUT, keeping its protection if it has one."""
    try:
        _save(pdf, out)
    except OSError as e:
        raise LabelError(tr("{path} cannot be written: {error}", path=out, error=e)) from None


def apply_all(pdf: Pdf, ranges: list[Range], view: View | None = None, changes=(), path: Path | None = None) -> None:
    """Give PDF these page labels, VIEW (if given: see view.write_view) and the header and footer
    CHANGES (headfoot.Change, in order; their variables see these labels and PATH)."""
    labels.write_labels(pdf, ranges)
    if view is not None:
        write_view(pdf, view)
    if changes:
        doc = headfoot.document_of(pdf, path, labels.page_labels(ranges, len(pdf.pages)))
        for change in changes:
            change.apply(pdf, doc)


def write_copy(source: Path, ranges: list[Range], target: Path, password: str = "",
               view: View | None = None, changes=()) -> None:
    """SOURCE with these page labels, VIEW and header and footer CHANGES (see apply_all), saved
    as TARGET (safely: TARGET may be SOURCE), keeping its protection if it has one."""
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        with pikepdf.open(source, password=password) as pdf:
            apply_all(pdf, ranges, view, changes, source)
            _save(pdf, tmp)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_list(name: str) -> list[str]:
    """The labels of a list (a file, or - for the standard input): one on each
    line, or as 'show --all' writes them, after the page numbers."""
    try:
        text = sys.stdin.read() if name == "-" else Path(name).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise LabelError(tr("{path} cannot be read: {error}", path=name, error=e)) from None
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    numbered = [re.fullmatch(r"\s*(\d+)(?:  (.*))?", line) for line in lines]
    if lines and all(numbered) and [int(m[1]) for m in numbered] == list(range(1, len(lines) + 1)):
        return [m[2] or "" for m in numbered]
    return lines
