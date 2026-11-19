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


def test_folios_and_suffixes(app, window, book):
    window.open_path(book)
    window._edit(1, style="f", start=23)  # (the range of page 9: folios from 12r)
    settle(app)
    assert window.ranges[1] == Range(9, "f", "", 23)
    assert window.pages.item(9).text().split() == ["10", "12v"]
    spin = window.table.cellWidget(1, 2)
    assert spin.text() == "12r" and spin.valueFromText("30v") == 60
    window._edit(0, prefix="[", suffix="]")
    settle(app)
    assert window.pages.item(1).text().split() == ["2", "[ii]"]
    assert window.save()
    assert ranges_of(book) == window.ranges  # (written one label for each page, and read back)
    assert "--range 1 style=roman" in window.cmd_line.text()


def test_password(app, window, book, monkeypatch):
    locked = book.with_name("locked.pdf")
    with pikepdf.open(book) as pdf:
        pdf.save(locked, encryption=pikepdf.Encryption(owner="o", user="u"))
    answers = iter(["wrong", "u"])
    monkeypatch.setattr(type(window), "ask_password", lambda self, path, again=False: next(answers))
    assert window.open_path(locked)
    assert window.password == "u" and window.ranges == [Range(1, "r"), Range(9, "D")]
    window.clear_labels()
    assert window.save()
    with pikepdf.open(locked, password="u") as pdf:  # (still protected)
        assert pdf.is_encrypted and labels.read_labels(pdf) == []
    monkeypatch.setattr(type(window), "ask_password", lambda self, path, again=False: None)
    assert not window.open_path(locked) and window.path == locked  # (cancelled: the document stays)


def test_copy_and_lists(app, window, book, tmp_path):
    other = tmp_path / "other.pdf"
    shutil.copyfile(EXAMPLE, other)
    window.open_path(other)
    assert window.copy_from(book)
    assert window.ranges == [Range(1, "r"), Range(9, "D")] and window.is_modified()
    listed = tmp_path / "labels.txt"
    assert window.export_list(listed)
    lines = listed.read_text().splitlines()
    assert lines[:2] == ["i", "ii"] and len(lines) == 100
    lines[49] = "Map"
    listed.write_text("\n".join(lines))
    assert window.import_list(listed)
    assert window.ranges == [Range(1, "r"), Range(9, "D"), Range(50, "", "Map"), Range(51, "D", "", 43)]
    listed.write_text("a\nb\n")
    assert not window.import_list(listed) and "2 labels" in window.statusBar().currentMessage()


def test_pages_list(app, window, book):
    window.open_path(book)
    window.start_range_at(30)
    assert window.ranges[-1] == Range(30) and window.table.currentRow() == 2
    window.start_range_at(9)  # (a range starts there: it is chosen)
    assert window.table.currentRow() == 1 and len(window.ranges) == 3
    assert window.go_to_label("iv") and window.current_page() == 4
    assert window.go_to_label("1") and window.current_page() == 9
    assert window.go_to_label("1") and window.current_page() == 30  # (Enter again: the next one)
    assert not window.go_to_label("xcix")
    window.a_thumbs.setChecked(True)
    for _ in range(40):
        app.processEvents()
    assert len(window._thumbs) == 100 and not window.pages.item(0).icon().isNull()
    assert window.pages.item(3).text() == "4\niv"
    window.a_thumbs.setChecked(False)


def select(window, pages):
    window.pages.clearSelection()
    window.pages.setCurrentRow(pages[0] - 1)
    for p in pages:
        window.pages.item(p - 1).setSelected(True)


def labels_of(window, first, last):
    return labels.page_labels(window.ranges, window.count)[first - 1:last]


def test_actions_on_chosen_pages(app, window, book, monkeypatch):
    window.open_path(book)
    select(window, [20, 21, 22])
    assert window.selected_pages() == [20, 21, 22]
    shown = [a.text() for a in window.build_pages_menu().actions()]
    assert "Number these pages…" in shown and "Edit their labels one by one…" in shown
    assert "Start a range at page 20" in shown

    window.ask_numbering = lambda count: ("A", "Plate ", 1, "")
    assert window.number_selected()
    assert labels_of(window, 19, 23) == ["11", "Plate A", "Plate B", "Plate C", "15"]
    assert window.selected_pages() == [20, 21, 22]  # (still chosen, for another action)
    assert window.continue_selected()
    assert labels_of(window, 19, 23) == ["11", "12", "13", "14", "15"]
    window.ask_text = lambda *a: "Map"
    assert window.label_selected()
    assert labels_of(window, 20, 22) == ["Map"] * 3
    window.ask_lines = lambda *a: "12\n12bis\n13\n"
    assert window.edit_selected()
    assert labels_of(window, 19, 23) == ["11", "12", "12bis", "13", "15"]
    window.ask_lines = lambda *a: "a\nb"
    assert not window.edit_selected() and "2 lines for 3 pages" in window.statusBar().currentMessage()
    window.copy_labels()
    assert QtWidgets.QApplication.clipboard().text() == "12\n12bis\n13"
    window.undo()
    assert labels_of(window, 20, 22) == ["Map"] * 3
    select(window, [1])
    assert not window.continue_selected()  # (page 1 has nothing before it)


def test_number_dialog(app, window):
    from py_foliation.gui.window import NumberDialog
    dlg = NumberDialog(window, 5)
    assert dlg.preview.text() == "1 … 5"
    dlg.style.setCurrentIndex(dlg.style.findData("f"))
    assert dlg.start.text() == "1r" and dlg.preview.text() == "1r … 3r"
    dlg.start.setValue(24)
    dlg.prefix.setText("f. ")
    assert dlg.values() == ("f", "f. ", 24, "") and dlg.preview.text() == "f. 12v … f. 14v"
    dlg.style.setCurrentIndex(dlg.style.findData("r"))
    assert dlg.start.text() == "12"  # (the leaf, as a number)


def test_view_when_opened(app, window, book):
    from py_foliation.view import View, read_view
    window.open_path(book)
    assert window.opening == View() and not window.is_modified()
    window.pages.setCurrentRow(8)
    menu = window.build_pages_menu()
    subs = {a.text(): a.menu() for a in menu.actions() if a.menu()}
    assert {"Page layout", "Page view"} <= set(subs)
    layouts = {a.text(): a for a in subs["Page layout"].actions()}
    assert list(layouts) == ["The viewer's choice", "Single", "Single Continuous", "Facing", "Facing Continuous",
                             "Cover", "Cover Continuous"] and layouts["The viewer's choice"].isChecked()
    layouts["Cover"].trigger()
    assert window.opening == View(layout="TwoPageRight") and window.is_modified()
    views = {a.text(): a for a in window.build_pages_menu().actions() if a.menu()}["Page view"].menu().actions()
    next(a for a in views if a.text() == "Fit to Width").trigger()
    assert window.opening == View("TwoPageRight", "FitH", 1)
    opener = next(a for a in window.build_pages_menu().actions() if a.text() == "Open the document at page 9")
    assert not opener.isChecked()
    opener.trigger()
    assert window.opening == View("TwoPageRight", "FitH", 9)
    window.undo()
    assert window.opening == View("TwoPageRight", "FitH", 1)
    window.redo()
    window.change([Range(1, "D")])  # (labels and view are saved together)
    assert window.save() and not window.is_modified()
    with pikepdf.open(book) as pdf:
        assert read_view(pdf) == View("TwoPageRight", "FitH", 9)
        assert labels.read_labels(pdf) == [Range(1, "D")]
    window._fill_view_menu()  # (the View menu has the same submenus, checked as they are now)
    sub = next(a.menu() for a in window.m_view.actions() if a.text() == "Page layout")
    assert next(a for a in sub.actions() if a.isChecked()).text() == "Cover"
    window.set_view_part("layout", "SinglePage")
    window.revert()
    assert window.opening == View("TwoPageRight", "FitH", 9)
    window.show_page(20)  # (the preview, window.view, still follows the page shown)
    assert window.view.pageNavigator().currentPage() == 19


def test_preview_settles_at_any_size(app, window, book):
    """At some sizes, a page fitted in the preview with scroll bars left to Qt made them show and hide
    without end, and the window stopped answering (py-foliation 0.6)."""
    from PySide6.QtCore import QElapsedTimer, QEvent, QObject

    toggles = [0]
    bars = (window.view.horizontalScrollBar(), window.view.verticalScrollBar())

    class Counter(QObject):
        def eventFilter(self, obj, event):
            if obj in bars and event.type() in (QEvent.Type.Show, QEvent.Type.Hide):
                toggles[0] += 1
            return False

    counter = Counter()
    app.installEventFilter(counter)
    try:
        window.open_path(book)
        window.show()
        for width in range(300, 380, 5):  # (sizes that toggled them, offscreen; on Wayland, others)
            window.resize(width, 460)
            toggles[0] = 0
            clock = QElapsedTimer()
            clock.start()
            while clock.elapsed() < 30:
                app.processEvents()
            assert toggles[0] <= 4, f"the scroll bars of the preview keep toggling at {width}x460"
    finally:
        app.removeEventFilter(counter)


def test_header_and_footer(app, window, book, monkeypatch):
    from py_foliation import headfoot
    from py_foliation.headfoot import HeaderFooter
    monkeypatch.setenv("PY_FOLIATION_CONFIG", str(book.parent / "cfg"))
    window.open_path(book)
    asked = []

    def ask(kind, hf, page, existing=False):
        asked.append((hf.pages, page))
        return HeaderFooter(footer_center="p. $pagelabel", pages=hf.pages), False

    window.ask_stamp = ask
    window.pages.setCurrentRow(8)
    window.pages.item(9).setSelected(True)
    menu = window.build_pages_menu()
    entry = next(a for a in menu.actions() if a.text() == "Header and footer on these pages…")
    entry.trigger()
    assert asked == [("9-10", 9)] and window.is_modified()
    assert window.pages_with_header_footer() == {9, 10}
    settle(app)
    assert window._previewed[1] == window.hf_changes  # (the preview shows a copy with them)
    window.undo()
    assert window.hf_changes == () and not window.is_modified()
    window.redo()
    assert window.save() and not window.is_modified() and window.pages_with() == {9, 10}
    with pikepdf.open(book) as pdf:
        assert headfoot.pages_with(pdf) == [9, 10]
        assert b"(p. 1)" in pdf.pages[8].obj.Contents[-1].read_bytes()
    assert window.undo_stack == []  # (the changes are in the file: the history would apply them again)
    assert window.remove_header_footer([10]) and window.pages_with_header_footer() == {9}
    window.revert()
    assert window.pages_with_header_footer() == {9, 10}
    headfoot.save_profile(HeaderFooter(header_right="$date", name="Dated", show_on_menu=True))
    window._fill_headfoot_menu()
    names = [a.text() for a in window.m_headfoot.actions()]
    assert names[:4] == ["Add…", "Update…", "Remove all", "Remove the Bates numbers"] and "Dated" in names
    next(a for a in window.m_headfoot.actions() if a.text() == "Dated").trigger()
    assert window.pages_with_header_footer() == set(range(1, 101))
    next(a for a in window.m_headfoot.actions() if a.text() == "Remove all").trigger()
    assert window.save()
    with pikepdf.open(book) as pdf:
        assert headfoot.pages_with(pdf) == []


def test_header_footer_dialog(app, window, book, monkeypatch):
    from py_foliation import headfoot
    from py_foliation.gui.headfoot_dialog import HeaderFooterDialog
    from py_foliation.headfoot import HeaderFooter
    monkeypatch.setenv("PY_FOLIATION_CONFIG", str(book.parent / "cfg"))
    labels_ = [str(i) for i in range(1, 101)]
    dlg = HeaderFooterDialog(window, HeaderFooter(footer_center="x", units="cm", top=2.54), book, "", labels_, 5)
    dlg.update_preview()
    assert dlg.problem.text() == "" and dlg.preview.pixmap() is not None and not dlg.preview.pixmap().isNull()
    dlg.slots["header_left"].setFocus()
    dlg.target = dlg.slots["header_left"]
    dlg.insert("$pagelabel")
    assert dlg.slots["header_left"].text() == "$pagelabel"
    dlg.units.setCurrentIndex(dlg.units.findData("in"))  # (the margins keep their place)
    assert dlg.margins["top"].value() == pytest.approx(1.0)
    dlg.some_pages.setChecked(True)
    dlg.pages.setText("10-20")
    dlg.parity.setCurrentIndex(dlg.parity.findData("odd"))
    hf, pages, problem = dlg.check()
    assert problem == "" and [p for p, _ in pages] == [11, 13, 15, 17, 19] and hf.units == "in"
    dlg.update_preview()
    assert dlg.note.text() == "The header and footer don't go on this page."  # (page 5)
    dlg.slots["footer_right"].setText("Ελλάς")
    dlg.update_preview()
    assert "cannot write" in dlg.problem.text()
    assert not dlg.buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).isEnabled()
    dlg.slots["footer_right"].setText("")
    monkeypatch.setattr(HeaderFooterDialog, "ask_profile_name", lambda self, current: "Mine")
    assert dlg.save_profile() and dlg.profile.currentData() == "Mine"
    assert headfoot.read_profiles()["Mine"].pages == "10-20"
    dlg.profile.setCurrentIndex(0)
    dlg.load(HeaderFooter(footer_left="y"))
    dlg.profile.setCurrentIndex(dlg.profile.findData("Mine"))  # (choosing a profile shows its settings)
    assert dlg.slots["header_left"].text() == "$pagelabel" and dlg.slots["footer_left"].text() == ""
    assert dlg.delete_profile() and headfoot.read_profiles() == {}
    dlg.reject()


def test_save_as_items(window, book, monkeypatch):
    from py_foliation import conform
    assert not window.output_actions[""].isEnabled() and not window.output_actions["a-2b"].isEnabled()
    window.open_path(book)
    assert window.output_actions[""].isEnabled() and window.a_save_as is window.output_actions[""]
    monkeypatch.setattr(conform, "command", lambda path=None: None)
    window._show_output()
    assert not window.output_actions["a-2b"].isEnabled() and "Needs pdf2iso" in \
        window.output_actions["x-4"].toolTip()
    asked = []
    window.export_dialog_as = lambda standard: asked.append(standard)
    monkeypatch.setattr(conform, "command", lambda path=None: ["pdf2iso"])
    window._show_output()
    window.output_actions["a-3b"].trigger()
    assert asked == ["a-3b"]


def test_export_refuses_the_open_file(window, book, monkeypatch):
    window.open_path(book)
    window.clear_labels()
    assert not window.export_as(book, "a-2b")
    assert ranges_of(book) == [Range(1, "r"), Range(9, "D")] and window.is_modified()


@pytest.mark.skipif(not shutil.which("pdf2iso"), reason="pdf2iso not installed")
def test_export_as_pdfx(window, book, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    window.warn = lambda title, text: pytest.fail(text)
    window.open_path(book)
    window.show_page(20)
    window.add_range()
    out = tmp_path / "print.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    window.output_actions["x-4"].trigger()
    assert b"GTS_PDFX" in out.read_bytes() and ranges_of(out) == window.ranges
    assert "PDF/X-4" in window.statusBar().currentMessage()
    # (an export: the window stays on the file, with its changes still to save)
    assert window.path == book and window.is_modified() and ranges_of(book) == [Range(1, "r"), Range(9, "D")]


def test_pdfconform_setting(window, book, tmp_path, monkeypatch):
    from py_foliation import config
    from py_foliation.gui.window import PdfconformDialog
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    window.open_path(book)
    assert not window.output_actions["a-2b"].isEnabled()
    d = PdfconformDialog("", window)
    assert "Not found" in d.found.text()
    d.edit.setText(str(tmp_path / "nothing"))
    assert "no such file" in d.found.text()
    script = tmp_path / "my-pdfconform"
    script.write_text("#!/bin/sh\n")
    d.edit.setText(str(script))
    assert str(script) in d.found.text()
    monkeypatch.setattr(PdfconformDialog, "exec", lambda self: QtWidgets.QDialog.DialogCode.Accepted)
    monkeypatch.setattr(PdfconformDialog, "path", lambda self: str(script))
    assert window.pdfconform_dialog()
    assert config.get("pdfconform") == str(script) and window.output_actions["a-2b"].isEnabled()
