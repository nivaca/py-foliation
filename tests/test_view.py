"""Tests of the view of a document when it is opened (view.py, and 'py-foliation view')."""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf
import pytest
from pikepdf import Array, Dictionary, Name

from py_foliation import config, interface, main
from py_foliation.labels import LabelError
from py_foliation.view import View, changed, parse_zoom, read_view, write_view

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "example" / "numbers-100.pdf"


@pytest.fixture(autouse=True)
def english(tmp_path, monkeypatch):
    monkeypatch.setenv(config.ENV, str(tmp_path / "cfg"))
    yield
    interface.use("en")
    interface.translate_argparse()


@pytest.fixture()
def book(tmp_path) -> Path:
    path = tmp_path / "book.pdf"
    shutil.copyfile(EXAMPLE, path)
    return path


def view_of(path: Path) -> View:
    with pikepdf.open(path) as pdf:
        return read_view(pdf)


@pytest.mark.parametrize("v", [
    View("TwoPageRight", "Fit", "UseThumbs", 5),
    View("OneColumn", "FitH", "", 100),
    View("", "150", "FullScreen", 1),
    View("SinglePage", "", "UseOutlines", 12),  # (a page at the viewer's zoom)
    View("TwoColumnLeft"),
    View(),
])
def test_write_and_read_back(book, v):
    with pikepdf.open(book, allow_overwriting_input=True) as pdf:
        write_view(pdf, v)
        pdf.save(book)
    assert view_of(book) == v


def test_a_zoom_opens_at_page_one():
    assert View(zoom="FitV").page == 1
    assert not View() and View(panel="UseNone")


def test_what_it_does_not_know_is_kept(book):
    with pikepdf.open(book, allow_overwriting_input=True) as pdf:
        pdf.Root.OpenAction = Dictionary(S=Name.JavaScript, JS=pikepdf.String("app.alert(1)"))
        pdf.Root.PageLayout = Name.TwoColumnLeft
        write_view(pdf, View(layout="SinglePage"))  # (only the layout changes)
        assert pdf.Root.OpenAction.S == Name.JavaScript
        write_view(pdf, View(layout="SinglePage", page=3))  # (a page replaces the action)
        assert isinstance(pdf.Root.OpenAction, Array)
        assert read_view(pdf) == View("SinglePage", "", "", 3)


def test_goto_actions_and_page_indexes(book):
    with pikepdf.open(book) as pdf:
        pdf.Root.OpenAction = Dictionary(S=Name.GoTo, D=Array([pdf.pages[6].obj, Name.FitB]))
        assert read_view(pdf) == View(zoom="FitB", panel="UseNone", page=7)  # (the example has no panel)
        pdf.Root.OpenAction = Array([2, Name.XYZ, None, None, 0])  # (a page index; zoom 0: the viewer's)
        assert read_view(pdf) == View(panel="UseNone", page=3)


def test_parsing():
    assert parse_zoom("150%") == parse_zoom(" 150 ") == "150"
    assert parse_zoom("fit-width") == parse_zoom("FitH") == "FitH"
    assert parse_zoom("default") == ""
    with pytest.raises(LabelError):
        parse_zoom("0%")
    with pytest.raises(LabelError, match="unknown layout"):
        changed(View(), 10, layout="sideways")
    v = changed(View(), 10, layout="double-cover", zoom="fit-page", page="LAST")
    assert v == View("TwoPageRight", "Fit", "", 10)
    assert changed(v, 10, panel="thumbnails") == View("TwoPageRight", "Fit", "UseThumbs", 10)  # (the rest kept)
    assert changed(View(zoom="Fit"), 10, zoom="default") == View()  # (page 1 was only there for the zoom)
    assert changed(View(zoom="Fit", page=4), 10, zoom="default") == View(page=4)


def test_view_command(book, capsys):
    assert main(["view", "--layout", "continuous", "--zoom", "fit-width", "--open-at", "9", str(book), "-i"]) == 0
    assert view_of(book) == View("OneColumn", "FitH", "UseNone", 9)  # (the example's panel is kept)
    capsys.readouterr()
    assert main(["view", str(book)]) == 0
    out = capsys.readouterr().out
    assert "Continuous" in out and "Fit the width" in out and "page 9" in out
    assert main(["show", str(book)]) == 0
    assert "When it is opened:" in capsys.readouterr().out
    assert main(["view", str(book), "--zoom", "200", "-n"]) == 0
    assert "200 %" in capsys.readouterr().out and view_of(book).zoom == "FitH"  # (dry run)
    assert main(["view", str(book), "--layout", "default", "--zoom", "default", "--panel", "default",
                 "--open-at", "default", "-i"]) == 0
    assert view_of(book) == View()


def test_view_command_errors(book, capsys):
    assert main(["view", str(book), "-i"]) == 1  # (nothing to change)
    assert main(["view", str(book), "--open-at", "101", "-i"]) == 1
    assert "not in the document" in capsys.readouterr().err
