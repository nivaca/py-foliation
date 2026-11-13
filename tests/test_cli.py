"""Tests of the command line (cli.py)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pikepdf
import pytest

from py_foliation import config, interface, labels, main
from py_foliation.labels import Range

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


def ranges_of(path: Path) -> list[Range]:
    with pikepdf.open(path) as pdf:
        return labels.read_labels(pdf)


def test_set_both_syntaxes(book, capsys):
    assert main(["set", str(book), "1:r", "9:D", "--range", "90-95", "style=A", "prefix=App-",
                 "LAST:-::Cover"]) == 0
    out = book.with_name("book-labelled.pdf")
    assert ranges_of(out) == [Range(1, "r"), Range(9, "D"), Range(90, "A", "App-"), Range(96, "D", "", 88),
                              Range(100, "", "Cover")]
    assert ranges_of(book) == []  # (the input is left alone)
    text = capsys.readouterr().out
    assert text.startswith(f"Wrote {out} (100 pages)") and "pages 90-95: App-A … App-F" in text


def test_set_replaces_or_keeps(book):
    assert main(["set", str(book), "1:r", "9:D", "-i"]) == 0
    assert main(["set", str(book), "50:A", "-i"]) == 0  # (replaced: pages 1-49 are 1, 2, 3 ...)
    assert ranges_of(book) == [Range(1), Range(50, "A")]
    assert main(["set", str(book), "1:r", "9:D", "-i"]) == 0
    assert main(["set", str(book), "--keep", "50:A", "-i"]) == 0
    assert ranges_of(book) == [Range(1, "r"), Range(9, "D"), Range(50, "A")]
    assert main(["set", str(book), "--remove", "50", "-i"]) == 0  # (--remove implies --keep)
    assert ranges_of(book) == [Range(1, "r"), Range(9, "D")]


def test_show(book, capsys):
    main(["set", str(book), "1:r", "9:D", "-i"])
    capsys.readouterr()
    assert main([str(book)]) == 0  # ("py-foliation file.pdf": show)
    out = capsys.readouterr().out
    assert "pages 1-8" in out and "i … viii" in out and "py-foliation set FILE.pdf 1:r 9:D" in out
    assert main(["show", "--all", str(book)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 100 and lines[8].split() == ["9", "1"]


def test_clear(book, capsys):
    main(["set", str(book), "1:r", "-i"])
    assert main(["clear", str(book), "-o", str(book.with_name("c.pdf"))]) == 0
    assert ranges_of(book.with_name("c.pdf")) == [] and ranges_of(book) == [Range(1, "r")]
    with pikepdf.open(book.with_name("c.pdf")) as pdf:
        assert "/PageLabels" not in pdf.Root


@pytest.mark.parametrize("args, message", [
    (["set", "{book}"], "no ranges given"),
    (["set", "{book}", "0:D"], "page 0 is not in the document"),
    (["set", "{book}", "9:Q"], "unknown style"),
    (["set", "{book}", "--range", "9", "colour=red"], "is not one of"),
    (["set", "{book}", "--remove", "5"], "no range starts at page 5"),
    (["set", "{book}", "1:D", "-o", "{book}"], "the output is the input file"),
    (["show", "missing.pdf"], "not found"),
])
def test_errors(book, capsys, args, message):
    assert main([a.replace("{book}", str(book)) for a in args]) == 1
    assert message in capsys.readouterr().err


def test_not_a_pdf(tmp_path, capsys):
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a PDF")
    assert main(["show", str(bad)]) == 1
    assert "cannot be read as a PDF" in capsys.readouterr().err


def test_interface_before_the_file(book, capsys):
    assert main(["--interface", "es", str(book)]) == 0  # (es is not taken for the file)
    assert "Sin etiquetas de página" in capsys.readouterr().out
