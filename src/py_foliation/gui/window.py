"""The main window: the ranges of page labels of a PDF, its pages with their
labels, and a preview of the page chosen."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pikepdf
from PySide6.QtCore import QByteArray, QPointF, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QVBoxLayout, QWidget,
)

from .. import __version__, config, interface, labels
from ..files import read_list, write_copy
from ..interface import tr
from ..labels import LabelError, Range
from . import thumbnails
from .widgets import FIELDS, LABELS, NumberDialog, edited_signal, fit_columns, range_row

RECENT = 10  # documents in File ▸ Open recent
AUTHOR = '<a href="https://nicolasvaughan.org">Nicolas Vaughan</a>'

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
        self._blank: QIcon | None = None
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
        self.pages.setToolTip(tr("Double-click a page to start a range at it; select pages (Shift, Ctrl) and "
                                 "right-click them for more"))
        self.pages.currentRowChanged.connect(self._page_chosen)
        self.pages.itemDoubleClicked.connect(lambda item: self.start_range_at(self.pages.row(item) + 1))
        self.pages.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.pages.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pages.customContextMenuRequested.connect(self.pages_menu)
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

    def _action(self, menu: QMenu, text: str, triggered, shortcut=None, tip: str = "") -> QAction:
        """A new action in MENU."""
        act = QAction(text, self, triggered=triggered)
        if shortcut is not None:
            act.setShortcut(shortcut)
        if tip:
            act.setToolTip(tip)
        menu.addAction(act)
        return act

    def _build_menus(self):
        m = self.menuBar().addMenu(tr("&File"))
        self._action(m, tr("Open…"), self.open_dialog, QKeySequence.StandardKey.Open)
        self.m_recent = m.addMenu(tr("Open recent"))
        self._recent_menu()
        self.a_save = self._action(m, tr("Save"), self.save, QKeySequence.StandardKey.Save,
                                   tr("Give the file open these page labels"))
        self.a_save_as = self._action(m, tr("Save as…"), self.save_as, "Ctrl+Shift+S",
                                      tr("Save a copy of the file with these page labels"))
        self.a_revert = self._action(m, tr("Revert to the labels of the file"), self.revert)
        m.addSeparator()
        self.a_copy_from = self._action(m, tr("Copy the labels of another PDF…"), self.copy_from_dialog,
                                        tip=tr("For instance, of an earlier export of the same book"))
        self.a_import = self._action(m, tr("Labels from a list…"), self.import_dialog,
                                     tip=tr("A text file with the label of each page, one on each line"))
        self.a_export = self._action(m, tr("Save the labels as a list…"), self.export_dialog,
                                     tip=tr("A text file with the label of each page, one on each line, to "
                                            "edit and read back"))
        m.setToolTipsVisible(True)
        m.addSeparator()
        self._action(m, tr("Quit"), self.close, QKeySequence.StandardKey.Quit)
        m = self.menuBar().addMenu(tr("&Edit"))
        self.a_undo = self._action(m, tr("Undo"), self.undo, QKeySequence.StandardKey.Undo)
        self.a_redo = self._action(m, tr("Redo"), self.redo, QKeySequence.StandardKey.Redo)
        m.addSeparator()
        self._action(m, tr("Copy command line"), self.copy_command_line)
        m.addSeparator()
        self._action(m, tr("Go to the page labelled…"), lambda: (self.go_to.setFocus(), self.go_to.selectAll()),
                     "Ctrl+L")
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
        self._action(m, tr("About"), self.about)
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

    @staticmethod
    def _filter(kind: str) -> str:
        return tr("PDF files (*.pdf)") if kind == "pdf" else tr("Text files (*.txt);;All files (*)")

    def _ask_open(self, title: str, kind: str = "pdf") -> Path | None:
        """A file to read, chosen by the user (KIND: pdf or text); None if none."""
        name, _ = QFileDialog.getOpenFileName(self, title, self.last_dir(), self._filter(kind))
        return Path(name) if name else None

    def _ask_save(self, title: str, default: str, kind: str = "pdf") -> Path | None:
        """A file to write (DEFAULT: its name, in the last folder used), chosen by the user; None if none."""
        name, _ = QFileDialog.getSaveFileName(self, title, str(Path(self.last_dir()) / default),
                                              self._filter(kind))
        return Path(name) if name else None

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
        path = self._ask_open(tr("Open PDF"))
        if path:
            self.open_path(path)

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
        target = self._ask_save(tr("Save as"), f"{self.path.stem}-labelled.pdf")
        if target is None:
            return False
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
        path = self._ask_open(tr("Copy the labels of another PDF"))
        if path:
            self.copy_from(path)

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
        path = self._ask_open(tr("Labels from a list"), "text")
        if path:
            self.import_list(path)

    def import_list(self, path: Path) -> bool:
        try:
            ranges = labels.from_list(read_list(str(path)), self.count)
        except LabelError as e:
            self.status(str(e), error=True)
            return False
        self.change(ranges)
        self.status(tr("Labels read from {path}", path=path.name))
        return True

    def export_dialog(self):
        if self.path is None:
            return
        path = self._ask_save(tr("Save the labels as a list"), f"{self.path.stem}-labels.txt", "text")
        if path:
            self.export_list(path)

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
        m = self.m_recent
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
        new = dataclasses.replace(old, **changes)
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

    # ----------------------------------------------------------------- actions on chosen pages

    def selected_pages(self) -> list[int]:
        """The pages chosen in the list (1-based, in order), or else the page shown."""
        rows = sorted(self.pages.row(item) for item in self.pages.selectedItems())
        if rows:
            return [r + 1 for r in rows]
        return [self.current_page()] if self.count else []

    def pages_menu(self, pos):
        if self.path is None:
            return
        item = self.pages.itemAt(pos)
        if item is not None and not item.isSelected():
            self.pages.setCurrentItem(item)
        menu = self.build_pages_menu()
        if menu is not None:
            menu.exec(self.pages.viewport().mapToGlobal(pos))

    def build_pages_menu(self) -> QMenu | None:
        """The menu of actions on the pages chosen."""
        pages = self.selected_pages()
        if not pages:
            return None
        menu = QMenu(self)
        count = len(pages)
        menu.addAction(tr("Number these pages…") if count > 1 else tr("Number this page…"),
                       lambda: self.number_selected())
        a = menu.addAction(tr("Continue the numbering from before"), lambda: self.continue_selected())
        a.setEnabled(pages[0] > 1)
        menu.addAction(tr("Give them one label…") if count > 1 else tr("Give it a label…"),
                       lambda: self.label_selected())
        if count > 1:
            menu.addAction(tr("Edit their labels one by one…"), lambda: self.edit_selected())
        menu.addAction(tr("No label"), lambda: self.change(labels.relabel(self.ranges, self.count,
                                                                          {p: "" for p in pages})))
        menu.addSeparator()
        menu.addAction(tr("Start a range at page {page}", page=pages[0]), lambda: self.start_range_at(pages[0]))
        menu.addAction(tr("Copy their labels") if count > 1 else tr("Copy its label"), lambda: self.copy_labels())
        return menu

    def ask_numbering(self, count: int) -> tuple[str, str, int, str] | None:
        dlg = NumberDialog(self, count)
        return dlg.values() if dlg.exec() == QDialog.DialogCode.Accepted else None

    def ask_text(self, title: str, label: str, text: str = "") -> str | None:
        value, ok = QInputDialog.getText(self, title, label, QLineEdit.EchoMode.Normal, text)
        return value if ok else None

    def ask_lines(self, title: str, label: str, text: str) -> str | None:
        value, ok = QInputDialog.getMultiLineText(self, title, label, text)
        return value if ok else None

    def number_selected(self) -> bool:
        pages = self.selected_pages()
        answer = self.ask_numbering(len(pages)) if pages else None
        if answer is None:
            return False
        style, prefix, start, suffix = answer
        self.change(labels.number_pages(self.ranges, self.count, pages, style, prefix, start, suffix))
        return True

    def continue_selected(self) -> bool:
        try:
            self.change(labels.continue_numbering(self.ranges, self.count, self.selected_pages()))
        except labels.LabelError as e:
            self.status(str(e), error=True)
            return False
        return True

    def label_selected(self) -> bool:
        pages = self.selected_pages()
        text = self.ask_text(tr("One label"), tr("The label of the pages chosen:"), self.label_of(pages[0]))
        if text is None:
            return False
        self.change(labels.relabel(self.ranges, self.count, {p: text for p in pages}))
        return True

    def edit_selected(self) -> bool:
        pages = self.selected_pages()
        text = self.ask_lines(tr("Their labels"), tr("The label of each page chosen, one on each line:"),
                              "\n".join(self.labels_of(pages)))
        if text is None:
            return False
        lines = text.split("\n")
        while len(lines) > len(pages) and not lines[-1].strip():
            lines.pop()
        if len(lines) != len(pages):
            self.status(tr("There are {lines} lines for {count} pages", lines=len(lines), count=len(pages)),
                        error=True)
            return False
        self.change(labels.relabel(self.ranges, self.count, dict(zip(pages, lines))))
        return True

    def copy_labels(self):
        QApplication.clipboard().setText("\n".join(self.labels_of(self.selected_pages())))
        self.status(tr("Labels copied"))

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
        self._fill_table(select)
        self._fill_pages()
        self.cmd_line.setText(labels.set_command(self.path, self.ranges) if self.path else "")
        self._show_page_info()
        self._update_title()
        self._enable()

    def _fill_table(self, select: int | None):
        """The table of ranges, with the range that starts at page SELECT chosen."""
        self._building = True
        self.table.setRowCount(0)
        spans = labels.spans(self.ranges, self.count)
        self.table.setRowCount(len(spans))
        for row, (r, last) in enumerate(spans):
            for col, w in range_row(r, last, self.count, first_row=row == 0).items():
                if col in FIELDS:
                    field, value = FIELDS[col]
                    edited_signal(w).connect(
                        lambda *_, row=row, w=w, field=field, value=value: self._edit(row, **{field: value(w)}))
                self.table.setCellWidget(row, col, w)
        fit_columns(self.table)
        rows = [i for i, (r, _) in enumerate(spans) if r.page == select]
        if rows:
            self.table.setCurrentCell(rows[0], LABELS)
        self._building = False

    def _fill_pages(self):
        """The list of pages with their labels (and their thumbnails, if they are shown), keeping the
        page shown and the pages chosen."""
        page = self.current_page()
        chosen = self.selected_pages()
        thumbs = self.a_thumbs.isChecked()
        self.pages.blockSignals(True)
        self.pages.clear()
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
            if len(chosen) > 1:  # (the pages chosen stay chosen, for another action on them)
                for p in chosen:
                    if p <= self.count:
                        self.pages.item(p - 1).setSelected(True)

    def show_thumbnails(self, on: bool):
        """Show the pages as thumbnails with their labels, or as a list."""
        mode = QListView.ViewMode.IconMode if on else QListView.ViewMode.ListMode
        self.pages.setViewMode(mode)
        self.pages.setIconSize(thumbnails.THUMB if on else QSize())
        self.pages.setGridSize(thumbnails.GRID if on else QSize())
        self.pages.setResizeMode(QListView.ResizeMode.Adjust)
        self.pages.setMovement(QListView.Movement.Static)
        self.pages.setWordWrap(on)
        self.pages.setUniformItemSizes(True)
        if not on:
            self.thumb_timer.stop()
        self.refresh()

    def _blank_thumb(self) -> QIcon:
        if self._blank is None:
            self._blank = thumbnails.blank()
        return self._blank

    def _draw_thumbnails(self):
        """Draw a few more thumbnails (in the background, so the window keeps answering)."""
        if not self.a_thumbs.isChecked() or self.doc.pageCount() == 0:
            self.thumb_timer.stop()
            return
        drawn = 0
        for page in range(1, self.count + 1):
            if page in self._thumbs:
                continue
            self._thumbs[page] = thumbnails.render(self.doc, page)
            item = self.pages.item(page - 1)
            if item is not None:
                item.setIcon(self._thumbs[page])
            drawn += 1
            if drawn >= thumbnails.AT_ONCE:
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
        page = self.current_page()
        self.status(tr("Page {page}, labelled {label}", page=page, label=self.label_of(page)))
        return True

    def labels_of(self, pages: list[int]) -> list[str]:
        """The labels of PAGES (1-based) with the ranges shown."""
        now = labels.page_labels(self.ranges, self.count)
        return [now[p - 1] for p in pages]

    def label_of(self, page: int) -> str:
        return self.labels_of([page])[0]

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
        spans = labels.spans(self.ranges, self.count)
        if not self._building and 0 <= row < len(spans):
            r, last = spans[row]
            if not r.page <= self.current_page() <= last:
                self.show_page(r.page)

    def _show_page_info(self):
        if not self.count:
            self.page_info.setText(tr("Open a PDF (File ▸ Open, or drop a file on the window)"))
            return
        page = self.current_page()
        label = self.label_of(page)
        self.page_info.setText(tr("Page {page} of {count} — label: {label}", page=page, count=self.count,
                                  label=label or tr("(no label)")))

    def _enable(self):
        has = self.path is not None
        for w in (self.b_add, self.b_remove, self.b_clear, self.a_save, self.a_save_as, self.a_revert,
                  self.a_copy_from, self.a_import, self.a_export, self.go_to):
            w.setEnabled(has)
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
