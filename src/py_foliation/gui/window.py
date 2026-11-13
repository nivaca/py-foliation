"""The main window: the ranges of page labels of a PDF, its pages with their
labels, and a preview of the page chosen."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import re

import pikepdf
from PySide6.QtCore import QByteArray, QPointF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPixmap, QValidator
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QTableWidget, QVBoxLayout, QWidget,
)

from .. import __version__, config, interface, labels
from ..cli import read_list, set_command
from ..interface import tr
from ..labels import LabelError, Range

RECENT = 10  # documents in File ▸ Open recent
AUTHOR = '<a href="https://nicolasvaughan.org">Nicolas Vaughan</a>'
FIRST, STYLE, START, PREFIX, SUFFIX, LABELS = range(6)  # the columns of the table of ranges
THUMB = QSize(96, 128)  # the largest thumbnail of a page
THUMBS_AT_ONCE = 8  # thumbnails drawn at each turn of the event loop

_WINDOWS: list = []  # (windows built again in another language must stay referenced)


def install_qt_translations():
    """Qt's own texts (file dialogs, standard buttons) in the language in use."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    app = QApplication.instance()
    for old in getattr(app, "_py_foliation_translators", []):
        app.removeTranslator(old)
    app._py_foliation_translators = []
    code = interface.code()
    QLocale.setDefault(QLocale(code))
    if code == "en":
        return
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name in ("qtbase", "qt"):
        t = QTranslator(app)
        if t.load(f"{name}_{code}", folder):
            app.installTranslator(t)
            app._py_foliation_translators.append(t)
            break


def header_width(table: QTableWidget, col: int) -> int:
    return table.horizontalHeader().fontMetrics().horizontalAdvance(table.horizontalHeaderItem(col).text()) + 16


def write_copy(source: Path, ranges: list[Range], target: Path, password: str = "") -> None:
    """SOURCE with these page labels, saved as TARGET (safely: TARGET may be SOURCE),
    keeping its protection if it has one."""
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        with pikepdf.open(source, password=password) as pdf:
            labels.write_labels(pdf, ranges)
            pdf.save(tmp, encryption=True if pdf.is_encrypted else None)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class StartSpin(QSpinBox):
    """The number a range starts at; for folios, a leaf and its side (12v)."""

    def __init__(self, folio: bool):
        super().__init__()
        self.folio = folio
        self.setRange(1, 999999)

    def textFromValue(self, value: int) -> str:
        return labels.to_folio(value) if self.folio else str(value)

    def valueFromText(self, text: str) -> int:
        if not self.folio:
            return int(text)
        m = re.fullmatch(r"\s*(\d+)\s*([rv]?)\s*", text)
        return 2 * int(m[1]) - (0 if m[2] == "v" else 1) if m and int(m[1]) else self.value()

    def validate(self, text: str, pos: int):
        if not self.folio:
            return super().validate(text, pos)
        if re.fullmatch(r"\s*[1-9]\d*\s*[rv]?\s*", text):
            return QValidator.State.Acceptable, text, pos
        return (QValidator.State.Intermediate if re.fullmatch(r"\s*\d*\s*", text)
                else QValidator.State.Invalid), text, pos


class MainWindow(QMainWindow):
    def __init__(self, state: dict | None = None):
        """STATE (from export_state) carries the document over when the window is
        built again, for instance in another language."""
        super().__init__()
        self.setAcceptDrops(True)
        self.settings = QSettings("py-foliation", "py-foliation")
        self.path: Path | None = None
        self.count = 0
        self.ranges: list[Range] = []  # (normalized)
        self.saved: list[Range] = []  # the labels of the file
        self.undo_stack: list[list[Range]] = []
        self.redo_stack: list[list[Range]] = []
        self.password = ""  # (of the document open)
        self._thumbs: dict[int, QIcon] = {}  # page (1-based) -> its thumbnail
        self._building = False
        self._build()
        self._build_menus()
        self._restore()
        self._update_title()
        if state:
            self.adopt_state(state)

    # ----------------------------------------------------------------- construction

    def _build(self):
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([tr("From page"), tr("Style"), tr("Starts at"), tr("Prefix"),
                                              tr("Suffix"), tr("Labels")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(LABELS, QHeaderView.ResizeMode.Stretch)
        self.table.currentCellChanged.connect(lambda row, *_: self._range_chosen(row))

        self.b_add = QPushButton(tr("Add a range"))
        self.b_add.setToolTip(tr("Start a new range at the page shown"))
        self.b_add.clicked.connect(self.add_range)
        self.b_remove = QPushButton(tr("Remove the range"))
        self.b_remove.setToolTip(tr("The range before goes on over its pages"))
        self.b_remove.clicked.connect(self.remove_range)
        self.b_clear = QPushButton(tr("No labels"))
        self.b_clear.setToolTip(tr("Remove all the page labels: viewers number the pages 1, 2, 3 ..."))
        self.b_clear.clicked.connect(self.clear_labels)
        buttons = QHBoxLayout()
        for b in (self.b_add, self.b_remove, self.b_clear):
            buttons.addWidget(b)
        buttons.addStretch(1)

        self.pages = QListWidget()
        self.pages.setToolTip(tr("Double-click a page to start a range at it"))
        self.pages.currentRowChanged.connect(self._page_chosen)
        self.pages.itemDoubleClicked.connect(lambda item: self.start_range_at(self.pages.row(item) + 1))
        self.thumb_timer = QTimer(self)
        self.thumb_timer.setInterval(0)
        self.thumb_timer.timeout.connect(self._draw_thumbnails)

        self.cmd_line = QLineEdit()
        self.cmd_line.setReadOnly(True)
        self.cmd_line.setToolTip(tr("The command that gives these labels to a file"))

        left = QWidget()
        lay = QVBoxLayout(left)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(QLabel("<b>" + tr("Ranges of page labels") + "</b>"))
        lay.addWidget(self.table, 2)
        lay.addLayout(buttons)
        lay.addWidget(QLabel("<b>" + tr("Pages and their labels") + "</b>"))
        lay.addWidget(self.pages, 3)
        lay.addWidget(QLabel(tr("Command line:")))
        lay.addWidget(self.cmd_line)

        self.doc = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.SinglePage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.page_info = QLabel("")
        self.go_to = QLineEdit()
        self.go_to.setPlaceholderText(tr("Go to the page labelled…"))
        self.go_to.setToolTip(tr("Type a label (xii, 12v, A-3) and press Enter; Enter again goes to the next "
                                 "page with that label"))
        self.go_to.setMinimumWidth(self.go_to.fontMetrics().horizontalAdvance(self.go_to.placeholderText()) + 24)
        self.go_to.returnPressed.connect(lambda: self.go_to_label(self.go_to.text()))
        top = QHBoxLayout()
        top.addWidget(self.page_info, 1)
        top.addWidget(self.go_to)
        right = QWidget()
        lay = QVBoxLayout(right)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)

        self.splitter = QSplitter()
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.setCentralWidget(self.splitter)
        self._enable()

    def _build_menus(self):
        m = self.menuBar().addMenu(tr("&File"))
        m.addAction(QAction(tr("Open…"), self, shortcut=QKeySequence.StandardKey.Open, triggered=self.open_dialog))
        self.m_recent = m.addMenu(tr("Open recent"))
        self._recent_menu()
        self.a_save = QAction(tr("Save"), self, shortcut=QKeySequence.StandardKey.Save, triggered=self.save)
        self.a_save.setToolTip(tr("Give the file open these page labels"))
        m.addAction(self.a_save)
        self.a_save_as = QAction(tr("Save as…"), self, shortcut="Ctrl+Shift+S", triggered=self.save_as)
        self.a_save_as.setToolTip(tr("Save a copy of the file with these page labels"))
        m.addAction(self.a_save_as)
        self.a_revert = QAction(tr("Revert to the labels of the file"), self, triggered=self.revert)
        m.addAction(self.a_revert)
        m.addSeparator()
        self.a_copy_from = QAction(tr("Copy the labels of another PDF…"), self, triggered=self.copy_from_dialog)
        self.a_copy_from.setToolTip(tr("For instance, of an earlier export of the same book"))
        m.addAction(self.a_copy_from)
        self.a_import = QAction(tr("Labels from a list…"), self, triggered=self.import_dialog)
        self.a_import.setToolTip(tr("A text file with the label of each page, one on each line"))
        m.addAction(self.a_import)
        self.a_export = QAction(tr("Save the labels as a list…"), self, triggered=self.export_dialog)
        self.a_export.setToolTip(tr("A text file with the label of each page, one on each line, to edit "
                                    "and read back"))
        m.addAction(self.a_export)
        m.setToolTipsVisible(True)
        m.addSeparator()
        m.addAction(QAction(tr("Quit"), self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close))
        m = self.menuBar().addMenu(tr("&Edit"))
        self.a_undo = QAction(tr("Undo"), self, shortcut=QKeySequence.StandardKey.Undo, triggered=self.undo)
        self.a_redo = QAction(tr("Redo"), self, shortcut=QKeySequence.StandardKey.Redo, triggered=self.redo)
        m.addAction(self.a_undo)
        m.addAction(self.a_redo)
        m.addSeparator()
        m.addAction(QAction(tr("Copy command line"), self, triggered=self.copy_command_line))
        m.addSeparator()
        a = QAction(tr("Go to the page labelled…"), self, shortcut="Ctrl+L",
                    triggered=lambda: (self.go_to.setFocus(), self.go_to.selectAll()))
        m.addAction(a)
        m = self.menuBar().addMenu(tr("&View"))
        self.a_thumbs = QAction(tr("Thumbnails of the pages"), self, checkable=True)
        self.a_thumbs.toggled.connect(self.show_thumbnails)
        m.addAction(self.a_thumbs)
        m = self.menuBar().addMenu(tr("&Settings"))
        lang = m.addMenu(tr("Interface Language"))
        group = QActionGroup(self)
        for code, name in interface.names().items():
            act = QAction(name, self, checkable=True)
            act.setChecked(code == interface.code())
            act.triggered.connect(lambda _=False, c=code: self.change_language(c))
            group.addAction(act)
            lang.addAction(act)
        m = self.menuBar().addMenu(tr("&Help"))
        m.addAction(QAction(tr("About"), self, triggered=self.about))
        self._enable()

    # ----------------------------------------------------------------- settings

    def _restore(self):
        geo = self.settings.value("geometry")
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        else:
            self.resize(1200, 800)
        split = self.settings.value("splitter")
        if isinstance(split, QByteArray):
            self.splitter.restoreState(split)
        self.a_thumbs.setChecked(self.settings.value("thumbnails", "false") == "true")

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("thumbnails", "true" if self.a_thumbs.isChecked() else "false")
        self.settings.sync()

    def closeEvent(self, event):
        if not self.maybe_discard():
            event.ignore()
            return
        self.save_settings()
        super().closeEvent(event)

    def export_state(self) -> dict:
        """What a new window needs to carry on with the same document."""
        return {"path": self.path, "ranges": self.ranges, "saved": self.saved, "undo": self.undo_stack,
                "redo": self.redo_stack, "page": self.current_page(), "password": self.password}

    def adopt_state(self, state: dict):
        if state["path"] is None:
            return
        self.password = state.get("password", "")
        self._load(state["path"], state["saved"])
        self.undo_stack, self.redo_stack = list(state["undo"]), list(state["redo"])
        self.ranges = state["ranges"]
        self.refresh()
        self.show_page(state["page"])

    def last_dir(self) -> str:
        return self.settings.value("last_dir", str(Path.home()))

    # ----------------------------------------------------------------- language

    def change_language(self, code: str):
        """Use CODE for the interface, keep it in the configuration file, and
        build the window again in that language."""
        if code == interface.code():
            return
        if not interface.use(code):
            QMessageBox.warning(self, tr("Interface Language"),
                                tr("The language of the interface could not be changed: {error}",
                                   error=interface.error()))
            interface.use(config.get("interface"))
            return
        try:
            config.set("interface", code)
        except OSError as e:
            self.status(tr("Could not keep the setting: {error}", error=e), error=True)
        install_qt_translations()
        self.save_settings()
        new = MainWindow(self.export_state())
        new.restoreGeometry(self.saveGeometry())
        new.show()
        _WINDOWS.append(new)
        self.path = None  # (nothing to ask about: the new window has it)
        self.hide()
        self.deleteLater()
        if self in _WINDOWS:
            _WINDOWS.remove(self)

    # ----------------------------------------------------------------- documents

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Open PDF"), self.last_dir(), tr("PDF files (*.pdf)"))
        if path:
            self.open_path(Path(path))

    def open_path(self, path: Path) -> bool:
        if not path.is_file():
            self.status(tr("{path} not found", path=path), error=True)
            return False
        if not self.maybe_discard():
            return False
        read = self.read_pdf(path)
        if read is None:
            return False
        saved, _, self.password = read
        self.settings.setValue("last_dir", str(path.parent))
        self.add_recent(path)
        self._load(path, saved)
        self.undo_stack, self.redo_stack = [], []
        self.ranges = list(saved)
        self.refresh()
        self.show_page(1)
        self.status(tr("Opened {path}", path=path))
        return True

    def read_pdf(self, path: Path) -> tuple[list[Range], int, str] | None:
        """(the labels, the number of pages, the password) of the PDF at PATH,
        asking for its password if it needs one; None if it can't be read."""
        password = ""
        while True:
            try:
                with pikepdf.open(path, password=password) as pdf:
                    return labels.read_labels(pdf), len(pdf.pages), password
            except pikepdf.PasswordError:
                password = self.ask_password(path, again=bool(password))
                if password is None:
                    self.status(tr("{path} is protected by a password", path=path), error=True)
                    return None
            except pikepdf.PdfError as e:
                self.status(tr("{path} cannot be read as a PDF: {error}", path=path, error=e), error=True)
                return None

    def ask_password(self, path: Path, again: bool = False) -> str | None:
        text = tr("That password is not right. The password of {name}:", name=path.name) if again \
            else tr("{name} is protected. Its password:", name=path.name)
        password, ok = QInputDialog.getText(self, tr("Password"), text, QLineEdit.EchoMode.Password)
        return password if ok and password else None

    def _load(self, path: Path, saved: list[Range]):
        self.doc.close()
        self.doc.setPassword(self.password)
        self.doc.load(str(path))
        self.path = path
        self.saved = list(saved)
        self._thumbs = {}
        with pikepdf.open(path, password=self.password) as pdf:
            self.count = len(pdf.pages)

    def save(self) -> bool:
        if self.path is None:
            return False
        return self._write(self.path)

    def save_as(self) -> bool:
        if self.path is None:
            return False
        name, _ = QFileDialog.getSaveFileName(self, tr("Save as"),
                                              str(Path(self.last_dir()) / f"{self.path.stem}-labelled.pdf"),
                                              tr("PDF files (*.pdf)"))
        if not name:
            return False
        target = Path(name)
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        self.settings.setValue("last_dir", str(target.parent))
        if not self._write(target):
            return False
        self.doc.close()
        self.doc.load(str(target))
        self.path = target
        self.add_recent(target)
        self._update_title()
        return True

    def _write(self, target: Path) -> bool:
        try:
            write_copy(self.path, self.ranges, target, self.password)
        except (OSError, pikepdf.PdfError) as e:
            self.status(tr("{path} cannot be written: {error}", path=target, error=e), error=True)
            return False
        if target == self.path:  # (the view keeps the file open: read it again)
            page = self.current_page()
            self.doc.close()
            self.doc.load(str(target))
            self.show_page(page)
        self.saved = list(self.ranges)
        self._update_title()
        self.status(tr("Saved {path}", path=target))
        return True

    def revert(self):
        if self.path is not None and self.ranges != self.saved:
            self.change(list(self.saved))

    def copy_from_dialog(self):
        if self.path is None:
            return
        name, _ = QFileDialog.getOpenFileName(self, tr("Copy the labels of another PDF"), self.last_dir(),
                                              tr("PDF files (*.pdf)"))
        if name:
            self.copy_from(Path(name))

    def copy_from(self, path: Path) -> bool:
        read = self.read_pdf(path)
        if read is None:
            return False
        ranges, count, _ = read
        self.change([r for r in ranges if r.page <= self.count])
        note = "" if count == self.count else " " + tr("(it has {count} pages)", count=count)
        self.status(tr("Labels copied from {path}", path=path.name) + note)
        return True

    def import_dialog(self):
        if self.path is None:
            return
        name, _ = QFileDialog.getOpenFileName(self, tr("Labels from a list"), self.last_dir(),
                                              tr("Text files (*.txt);;All files (*)"))
        if name:
            self.import_list(Path(name))

    def import_list(self, path: Path) -> bool:
        try:
            listed = read_list(str(path))
            if len(listed) != self.count:
                raise LabelError(tr("the list has {labels} labels, but the document has {count} pages",
                                    labels=len(listed), count=self.count))
        except LabelError as e:
            self.status(str(e), error=True)
            return False
        self.change(labels.from_labels(listed))
        self.status(tr("Labels read from {path}", path=path.name))
        return True

    def export_dialog(self):
        if self.path is None:
            return
        name, _ = QFileDialog.getSaveFileName(self, tr("Save the labels as a list"),
                                              str(Path(self.last_dir()) / f"{self.path.stem}-labels.txt"),
                                              tr("Text files (*.txt);;All files (*)"))
        if name:
            self.export_list(Path(name))

    def export_list(self, path: Path) -> bool:
        try:
            path.write_text("\n".join(labels.page_labels(self.ranges, self.count)) + "\n", encoding="utf-8")
        except OSError as e:
            self.status(tr("{path} cannot be written: {error}", path=path, error=e), error=True)
            return False
        self.status(tr("Saved {path}", path=path))
        return True

    # ----------------------------------------------------------------- recent files

    def recent_files(self) -> list[Path]:
        try:
            names = json.loads(self.settings.value("recent", "[]"))
        except (TypeError, ValueError):
            names = []
        return [Path(n) for n in names if isinstance(n, str)][:RECENT]

    def _set_recent(self, paths: list[Path]):
        self.settings.setValue("recent", json.dumps([str(p) for p in paths[:RECENT]]))
        self._recent_menu()

    def add_recent(self, path: Path):
        path = path.resolve()
        self._set_recent([path] + [p for p in self.recent_files() if p != path])

    def clear_recent(self):
        self._set_recent([])

    def _recent_menu(self):
        m = getattr(self, "m_recent", None)
        if m is None:
            return
        m.clear()
        paths = self.recent_files()
        for i, path in enumerate(paths, 1):
            key = f"&{i}" if i < 10 else "1&0"
            act = m.addAction(f"{key} " + path.name.replace("&", "&&"), lambda p=path: self.open_path(p))
            act.setToolTip(str(path))
            act.setStatusTip(str(path))
        if paths:
            m.addSeparator()
        m.addAction(tr("Clear the list"), self.clear_recent).setEnabled(bool(paths))
        m.setToolTipsVisible(True)

    # ----------------------------------------------------------------- changing the ranges

    def change(self, ranges: list[Range], select: int | None = None):
        """Make RANGES the labels (undoably); SELECT: the first page of the range to select."""
        ranges = labels.normalize(ranges)
        if ranges == self.ranges:
            self.refresh(select)
            return
        self.undo_stack.append(self.ranges)
        self.redo_stack.clear()
        self.ranges = ranges
        self.refresh(select)

    def _edit(self, row: int, **changes):
        """Change one field of the range in ROW (later, out of the signal of the widget)."""
        if self._building or not 0 <= row < len(self.ranges):
            return
        old = self.ranges[row]
        new = Range(**{**vars(old), **changes})
        ranges = [r for r in self.ranges if r.page not in (old.page, new.page)] + [new]
        QTimer.singleShot(0, lambda: self.change(ranges, select=new.page))

    def start_range_at(self, page: int):
        """Select the range that starts at PAGE, or start one there."""
        if self.path is None:
            return
        if page in {r.page for r in self.ranges} or (page == 1 and not self.ranges):
            self.refresh(select=page)
            return
        self.change(self.ranges + [Range(page)], select=page)

    def add_range(self):
        if self.path is None:
            return
        starts = {r.page for r in self.ranges} or {1}
        page = self.current_page()
        while page in starts and page < self.count:
            page += 1
        if page in starts:
            self.status(tr("Every page already starts a range"), error=True)
            return
        self.change(self.ranges + [Range(page)], select=page)

    def remove_range(self):
        row = self.table.currentRow()
        if not 0 < row < len(self.ranges):
            self.status(tr("Choose a range after the first one"), error=True)
            return
        page = self.ranges[row].page
        self.change(labels.apply(self.ranges, [], self.count, [page]), select=self.ranges[row - 1].page)

    def clear_labels(self):
        if self.path is not None:
            self.change([])

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.ranges)
            self.ranges = self.undo_stack.pop()
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.ranges)
            self.ranges = self.redo_stack.pop()
            self.refresh()

    # ----------------------------------------------------------------- showing

    def refresh(self, select: int | None = None):
        """Show the ranges, the labels of the pages and the command line."""
        if select is None:
            row = self.table.currentRow()
            select = self.ranges[row].page if 0 <= row < len(self.ranges) else None
        self._building = True
        self.table.setRowCount(0)
        spans = labels.spans(self.ranges, self.count)
        self.table.setRowCount(len(spans))
        for row, (r, last) in enumerate(spans):
            first = QSpinBox()
            first.setRange(1, max(self.count, 1))
            first.setValue(r.page)
            first.setEnabled(row > 0)  # (the first range starts at page 1)
            first.setToolTip(tr("The first page of the range (the pages of the file, from 1)"))
            first.editingFinished.connect(lambda row=row, w=first: self._edit(row, page=w.value()))
            style = QComboBox()
            for code in labels.STYLES:
                style.addItem(tr(labels.STYLE_TITLES[code]), code)
            style.setCurrentIndex(labels.STYLES.index(r.style))
            style.currentIndexChanged.connect(
                lambda _i, row=row, w=style: self._edit(row, style=w.currentData()))
            start = StartSpin(r.style == "f")
            start.setValue(r.start)
            start.setEnabled(bool(r.style))
            start.setToolTip(tr("The leaf and side of the first page of the range (12r, 12v)") if r.style == "f"
                             else tr("The number of the first page of the range"))
            start.editingFinished.connect(lambda row=row, w=start: self._edit(row, start=w.value()))
            prefix = QLineEdit(r.prefix)
            prefix.setMinimumWidth(110)
            prefix.setPlaceholderText(tr("e.g. A-"))
            prefix.setToolTip(tr("Text put before the number of each page"))
            prefix.editingFinished.connect(lambda row=row, w=prefix: self._edit(row, prefix=w.text()))
            suffix = QLineEdit(r.suffix)
            suffix.setMinimumWidth(70)
            suffix.setEnabled(bool(r.style))
            suffix.setPlaceholderText(tr("e.g. ]"))
            suffix.setToolTip(tr("Text put after the number of each page (PDF has no suffixes: such labels "
                                 "are written one for each page)"))
            suffix.editingFinished.connect(lambda row=row, w=suffix: self._edit(row, suffix=w.text()))
            for col, w in ((FIRST, first), (STYLE, style), (START, start), (PREFIX, prefix), (SUFFIX, suffix)):
                self.table.setCellWidget(row, col, w)
            pages = tr("pages {first}-{last}", first=r.page, last=last) if last > r.page \
                else tr("page {first}", first=r.page)
            item = QLabel(f"{labels.describe(r, last)}   ({pages})")
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setContentsMargins(6, 0, 6, 0)
            self.table.setCellWidget(row, LABELS, item)
        for col in (FIRST, STYLE, START, PREFIX, SUFFIX):  # (cell widgets: ResizeToContents ignores them)
            widths = [self.table.cellWidget(row, col).sizeHint().width() for row in range(len(spans))]
            self.table.setColumnWidth(col, max(widths + [header_width(self.table, col)]) + 4)
        rows = [i for i, (r, _) in enumerate(spans) if r.page == select]
        if rows:
            self.table.setCurrentCell(rows[0], LABELS)
        self._building = False

        page = self.current_page()
        self.pages.blockSignals(True)
        self.pages.clear()
        thumbs = self.a_thumbs.isChecked() if hasattr(self, "a_thumbs") else False
        for i, label in enumerate(labels.page_labels(self.ranges, self.count), 1):
            item = QListWidgetItem(f"{i}\n{label}" if thumbs else f"{i:>5}   {label}")
            item.setToolTip(tr("page {page} of the file: {label}", page=i, label=label or tr("(no label)")))
            if thumbs:
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                item.setIcon(self._thumbs.get(i) or self._blank_thumb())
            self.pages.addItem(item)
        self.pages.blockSignals(False)
        if thumbs and len(self._thumbs) < self.count:
            self.thumb_timer.start()
        if self.count:
            self.pages.setCurrentRow(min(page, self.count) - 1)
        self.cmd_line.setText(set_command(self.path, self.ranges) if self.path else "")
        self._show_page_info()
        self._update_title()
        self._enable()

    def show_thumbnails(self, on: bool):
        """Show the pages as thumbnails with their labels, or as a list."""
        mode = QListView.ViewMode.IconMode if on else QListView.ViewMode.ListMode
        self.pages.setViewMode(mode)
        self.pages.setIconSize(THUMB if on else QSize())
        self.pages.setGridSize(QSize(THUMB.width() + 28, THUMB.height() + 48) if on else QSize())
        self.pages.setResizeMode(QListView.ResizeMode.Adjust)
        self.pages.setMovement(QListView.Movement.Static)
        self.pages.setWordWrap(on)
        self.pages.setUniformItemSizes(True)
        if not on:
            self.thumb_timer.stop()
        self.refresh()

    def _blank_thumb(self) -> QIcon:
        """What a page shows until its thumbnail is drawn (of the full size, so the grid doesn't move)."""
        if getattr(self, "_blank", None) is None:
            pixmap = QPixmap(THUMB)
            pixmap.fill(QColor(0, 0, 0, 0))
            self._blank = QIcon(pixmap)
        return self._blank

    def _thumbnail(self, page: int) -> QIcon:
        """The thumbnail of PAGE (1-based), framed, centred in a THUMB-sized picture."""
        size = self.doc.pagePointSize(page - 1).toSize().scaled(THUMB - QSize(2, 2), Qt.AspectRatioMode.KeepAspectRatio)
        if size.isEmpty():
            size = THUMB - QSize(2, 2)
        image = self.doc.render(page - 1, size)
        pixmap = QPixmap(THUMB)
        pixmap.fill(QColor(0, 0, 0, 0))
        p = QPainter(pixmap)
        x, y = (THUMB.width() - size.width()) // 2, THUMB.height() - size.height() - 1
        p.fillRect(x, y, size.width(), size.height(), QColor("white"))
        p.drawImage(x, y, image)
        p.setPen(QColor(128, 128, 128))
        p.drawRect(x - 1, y - 1, size.width() + 1, size.height() + 1)
        p.end()
        return QIcon(pixmap)

    def _draw_thumbnails(self):
        """Draw a few more thumbnails (in the background, so the window keeps answering)."""
        if not self.a_thumbs.isChecked() or self.doc.pageCount() == 0:
            self.thumb_timer.stop()
            return
        drawn = 0
        for page in range(1, self.count + 1):
            if page in self._thumbs:
                continue
            self._thumbs[page] = self._thumbnail(page)
            item = self.pages.item(page - 1)
            if item is not None:
                item.setIcon(self._thumbs[page])
            drawn += 1
            if drawn >= THUMBS_AT_ONCE:
                return
        self.thumb_timer.stop()

    def go_to_label(self, label: str) -> bool:
        """Show the page labelled LABEL (the next one after the page shown, if there are several)."""
        if not self.count or not label.strip():
            return False
        pages = labels.find_label(self.ranges, self.count, label.strip())
        if not pages:
            self.status(tr("No page is labelled {label}", label=label.strip()), error=True)
            return False
        here = self.current_page()
        self.show_page(next((p for p in pages if p > here), pages[0]))
        self.status(tr("Page {page}, labelled {label}", page=self.current_page(),
                       label=labels.page_labels(self.ranges, self.count)[self.current_page() - 1]))
        return True

    def current_page(self) -> int:
        row = self.pages.currentRow()
        return row + 1 if row >= 0 else 1

    def show_page(self, page: int):
        if self.count:
            self.pages.setCurrentRow(max(1, min(page, self.count)) - 1)

    def _page_chosen(self, row: int):
        if row < 0 or not self.count:
            return
        nav = self.view.pageNavigator()
        if row < self.doc.pageCount():
            nav.jump(row, QPointF(), nav.currentZoom())
        self._show_page_info()

    def _range_chosen(self, row: int):
        if not self._building and 0 <= row < len(self.ranges):
            page = self.ranges[row].page
            if not (page <= self.current_page() < (self.ranges[row + 1].page if row + 1 < len(self.ranges)
                                                   else self.count + 1)):
                self.show_page(page)

    def _show_page_info(self):
        if not self.count:
            self.page_info.setText(tr("Open a PDF (File ▸ Open, or drop a file on the window)"))
            return
        page = self.current_page()
        label = labels.page_labels(self.ranges, self.count)[page - 1]
        self.page_info.setText(tr("Page {page} of {count} — label: {label}", page=page, count=self.count,
                                  label=label or tr("(no label)")))

    def _enable(self):
        has = self.path is not None
        for w in (getattr(self, n, None) for n in ("b_add", "b_remove", "b_clear", "a_save", "a_save_as",
                                                   "a_revert", "a_copy_from", "a_import", "a_export",
                                                   "go_to")):
            if w is not None:
                w.setEnabled(has)
        if hasattr(self, "a_undo"):
            self.a_undo.setEnabled(bool(self.undo_stack))
            self.a_redo.setEnabled(bool(self.redo_stack))

    # ----------------------------------------------------------------- unsaved changes

    def is_modified(self) -> bool:
        return self.path is not None and self.ranges != self.saved

    def _update_title(self):
        name = f"{self.path.name}[*] — py-foliation" if self.path else "py-foliation"
        self.setWindowTitle(name)
        self.setWindowModified(self.is_modified())

    def ask_unsaved(self) -> QMessageBox.StandardButton:
        box = QMessageBox(QMessageBox.Icon.Warning, tr("Unsaved changes"),
                          tr("The new page labels haven't been saved. Save them before going on?"),
                          QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                          | QMessageBox.StandardButton.Cancel, self)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def maybe_discard(self) -> bool:
        """True if it is all right to go on (nothing unsaved, saved now, or discarded)."""
        if not self.is_modified():
            return True
        answer = self.ask_unsaved()
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    # ----------------------------------------------------------------- drag and drop

    def dragEnterEvent(self, event):
        if any(u.toLocalFile().lower().endswith(".pdf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for u in event.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.open_path(Path(u.toLocalFile()))
                break

    # ----------------------------------------------------------------- messages

    def status(self, text: str, error: bool = False):
        self.statusBar().setStyleSheet("color: #c0392b;" if error else "")
        self.statusBar().showMessage(text, 0 if error else 8000)

    def copy_command_line(self):
        QApplication.clipboard().setText(self.cmd_line.text())
        self.status(tr("Command line copied"))

    def about(self):
        QMessageBox.about(self, tr("About py-foliation"),
                          tr("<b>py-foliation {version}</b><p>Changes the page labels of PDF documents: the "
                             "numbering a PDF viewer shows for their pages.</p><p>By {author}.</p><p>Licensed "
                             "under the GNU General Public License, version 3 or later.</p>",
                             version=__version__, author=AUTHOR))
