"""The main window: the ranges of page labels of a PDF, its pages with their
labels, and a preview of the page chosen."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pikepdf
from PySide6.QtCore import QByteArray, QPointF, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget,
    QVBoxLayout, QWidget,
)

from .. import __version__, config, interface, labels
from ..cli import set_command
from ..interface import tr
from ..labels import Range

RECENT = 10  # documents in File ▸ Open recent
AUTHOR = '<a href="https://nicolasvaughan.org">Nicolas Vaughan</a>'
FIRST, STYLE, START, PREFIX, LABELS = range(5)  # the columns of the table of ranges

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


def write_copy(source: Path, ranges: list[Range], target: Path) -> None:
    """SOURCE with these page labels, saved as TARGET (safely: TARGET may be SOURCE)."""
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
    os.close(fd)
    try:
        with pikepdf.open(source) as pdf:
            labels.write_labels(pdf, ranges)
            pdf.save(tmp)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
        self._building = False
        self._build()
        self._build_menus()
        self._restore()
        self._update_title()
        if state:
            self.adopt_state(state)

    # ----------------------------------------------------------------- construction

    def _build(self):
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([tr("From page"), tr("Style"), tr("Starts at"), tr("Prefix"),
                                              tr("Labels")])
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
        self.pages.currentRowChanged.connect(self._page_chosen)

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
        right = QWidget()
        lay = QVBoxLayout(right)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.page_info)
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
        m = self.menuBar().addMenu(tr("&Settings"))
        lang = m.addMenu(tr("Language of the interface"))
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

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
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
                "redo": self.redo_stack, "page": self.current_page()}

    def adopt_state(self, state: dict):
        if state["path"] is None:
            return
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
            QMessageBox.warning(self, tr("Language of the interface"),
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
        try:
            with pikepdf.open(path) as pdf:
                saved = labels.read_labels(pdf)
        except pikepdf.PasswordError:
            self.status(tr("{path} is protected by a password", path=path), error=True)
            return False
        except pikepdf.PdfError as e:
            self.status(tr("{path} cannot be read as a PDF: {error}", path=path, error=e), error=True)
            return False
        self.settings.setValue("last_dir", str(path.parent))
        self.add_recent(path)
        self._load(path, saved)
        self.undo_stack, self.redo_stack = [], []
        self.ranges = list(saved)
        self.refresh()
        self.show_page(1)
        self.status(tr("Opened {path}", path=path))
        return True

    def _load(self, path: Path, saved: list[Range]):
        self.doc.close()
        self.doc.load(str(path))
        self.path = path
        self.saved = list(saved)
        with pikepdf.open(path) as pdf:
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
            write_copy(self.path, self.ranges, target)
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
            start = QSpinBox()
            start.setRange(1, 999999)
            start.setValue(r.start)
            start.setEnabled(bool(r.style))
            start.setToolTip(tr("The number of the first page of the range"))
            start.editingFinished.connect(lambda row=row, w=start: self._edit(row, start=w.value()))
            prefix = QLineEdit(r.prefix)
            prefix.setMinimumWidth(110)
            prefix.setPlaceholderText(tr("e.g. A-"))
            prefix.setToolTip(tr("Text put before the number of each page"))
            prefix.editingFinished.connect(lambda row=row, w=prefix: self._edit(row, prefix=w.text()))
            for col, w in ((FIRST, first), (STYLE, style), (START, start), (PREFIX, prefix)):
                self.table.setCellWidget(row, col, w)
            pages = tr("pages {first}-{last}", first=r.page, last=last) if last > r.page \
                else tr("page {first}", first=r.page)
            item = QLabel(f"{labels.describe(r, last)}   ({pages})")
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setContentsMargins(6, 0, 6, 0)
            self.table.setCellWidget(row, LABELS, item)
        for col in (FIRST, STYLE, START, PREFIX):  # (cell widgets: ResizeToContents ignores them)
            widths = [self.table.cellWidget(row, col).sizeHint().width() for row in range(len(spans))]
            self.table.setColumnWidth(col, max(widths + [header_width(self.table, col)]) + 4)
        rows = [i for i, (r, _) in enumerate(spans) if r.page == select]
        if rows:
            self.table.setCurrentCell(rows[0], LABELS)
        self._building = False

        page = self.current_page()
        self.pages.blockSignals(True)
        self.pages.clear()
        for i, label in enumerate(labels.page_labels(self.ranges, self.count), 1):
            item = QListWidgetItem(f"{i:>5}   {label}")
            if label != str(i):
                item.setToolTip(tr("page {page} of the file: {label}", page=i, label=label))
            self.pages.addItem(item)
        self.pages.blockSignals(False)
        if self.count:
            self.pages.setCurrentRow(min(page, self.count) - 1)
        self.cmd_line.setText(set_command(self.path, self.ranges) if self.path else "")
        self._show_page_info()
        self._update_title()
        self._enable()

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
                                                   "a_revert")):
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
