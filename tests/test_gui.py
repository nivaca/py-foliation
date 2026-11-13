"""Tests of the window (run headless with the Qt 'offscreen' platform)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pikepdf
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtPdfWidgets")

from py_foliation import interface, labels  # noqa: E402
from py_foliation.labels import Range  # noqa: E402

EXAMPLE = Path(__file__).resolve().parent.parent / "docs" / "example" / "numbers-100.pdf"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtCore import QCoreApplication
    QCoreApplication.setOrganizationName("py-foliation-tests")
    QCoreApplication.setApplicationName("py-foliation-tests")
    yield QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture()
def window(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QMessageBox
    from py_foliation.gui.window import MainWindow
    monkeypatch.setenv("PY_FOLIATION_CONFIG", str(tmp_path / "cfg"))
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(tmp_path / "settings"))
    # (no modal question in the tests: unsaved work is discarded, unless a test says otherwise)
    monkeypatch.setattr(MainWindow, "ask_unsaved", lambda self: QMessageBox.StandardButton.Discard)
    w = MainWindow()
    yield w
    try:
        w.close()
    except RuntimeError:  # (already deleted: the window was built again in another language)
        pass
    interface.use("en")


@pytest.fixture()
def book(tmp_path) -> Path:
    path = tmp_path / "book.pdf"
    shutil.copyfile(EXAMPLE, path)
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        labels.write_labels(pdf, [Range(1, "r"), Range(9, "D")])
        pdf.save(path)
    return path


def settle(app):
    for _ in range(3):
        app.processEvents()


def ranges_of(path: Path) -> list[Range]:
    with pikepdf.open(path) as pdf:
        return labels.read_labels(pdf)


def test_open_shows_the_labels(window, book):
    assert window.open_path(book)
    assert window.count == 100 and window.ranges == [Range(1, "r"), Range(9, "D")]
    assert window.table.rowCount() == 2
    assert window.pages.item(8).text().split() == ["9", "1"]
    assert window.cmd_line.text().endswith("book.pdf 1:r 9:D")
    assert not window.is_modified()


def test_edit_undo_and_save(app, window, book):
    window.open_path(book)
    window.show_page(50)
    window.add_range()
    assert window.ranges[-1] == Range(50) and window.is_modified()
    window._edit(2, style="A", prefix="App-")
    settle(app)
    assert window.ranges[-1] == Range(50, "A", "App-")
    assert window.pages.item(49).text().split() == ["50", "App-A"]
    window.undo()
    assert window.ranges[-1] == Range(50)
    window.redo()
    window.table.setCurrentCell(1, 0)
    window.remove_range()
    assert window.ranges == [Range(1, "r"), Range(50, "A", "App-")]
    assert window.save()
    assert ranges_of(book) == window.ranges and not window.is_modified()
    window.clear_labels()
    window.revert()
    assert window.ranges == ranges_of(book)


def test_first_page_and_merging(app, window, book):
    window.open_path(book)
    window._edit(1, page=5)  # (the range of page 9 now starts at 5)
    settle(app)
    assert window.ranges == [Range(1, "r"), Range(5, "D")]
    window._edit(1, page=1)  # (moved onto the first range: it replaces it)
    settle(app)
    assert window.ranges == [Range(1, "D")]


def test_save_as_and_unsaved(window, book, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    window.open_path(book)
    window.clear_labels()
    target = book.with_name("copy")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    assert window.save_as()
    assert window.path == target.with_suffix(".pdf") and ranges_of(window.path) == []
    assert ranges_of(book) == [Range(1, "r"), Range(9, "D")]
    window.show_page(20)
    window.add_range()
    window.ask_unsaved = lambda: QMessageBox.StandardButton.Cancel
    assert not window.open_path(book)  # (cancelled: the changes stay)
    assert window.is_modified()
    window.ask_unsaved = lambda: QMessageBox.StandardButton.Save
    assert window.open_path(book)
    assert ranges_of(target.with_suffix(".pdf")) == [Range(1), Range(20, "D")]


def test_language(window, book, tmp_path):
    from py_foliation.gui import window as module
    window.open_path(book)
    window.add_range()
    window.change_language("es")
    new = module._WINDOWS[-1]
    assert new is not window and interface.code() == "es"
    assert new.ranges == [Range(1, "r"), Range(2), Range(9, "D")] and new.undo_stack
    assert new.is_modified() and new.path == book
    assert new.table.horizontalHeaderItem(1).text() == "Estilo"
    assert (tmp_path / "cfg" / "config.toml").read_text().count('interface = "es"') == 1
    new.ask_unsaved = window.ask_unsaved
    new.close()


def test_icon(app):
    from py_foliation.gui import app_icon
    icon = app_icon()
    assert not icon.isNull() and len(icon.availableSizes()) >= 10
