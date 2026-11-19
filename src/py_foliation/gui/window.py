"""The main window: the ranges of page labels of a PDF, its pages with their
labels, and a preview of the chosen page."""

from __future__ import annotations

import dataclasses
from collections import OrderedDict
import json
import tempfile
from pathlib import Path

import pikepdf
from PySide6.QtCore import (
    QByteArray, QEvent, QItemSelection, QItemSelectionModel, QPoint, QPointF, QSettings, Qt, QTimer,
)
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QVBoxLayout, QWidget,
)

from .. import __version__, arrange, conform, config, files, headfoot, interface, labels, stamps, view, watermark
from ..changes import Change
from ..view import View, read_view
from ..files import read_list, write_copy
from ..interface import N_, ntr, tr
from ..labels import LabelError, Range
from . import thumbnails
from .arrange_dialog import PageList, ask_arrange, ask_labels
from .headfoot_dialog import ask_header_footer
from .thumb_renderer import Job, ThumbRenderer
from .thumbs_panel import ThumbsPanel
from .watermark_dialog import ask_watermark
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


# The operations on the pages, each with its dialog (the Pages menu, and "More" in the others).
ARRANGE_MENU = (("rotate", N_("Rotate…")), ("delete", N_("Delete…")), ("move", N_("Move…")),
                ("duplicate", N_("Duplicate…")), ("reverse", N_("Reverse the order…")),
                ("order", N_("New order…")), (None, None),
                ("blank", N_("Insert blank pages…")), ("insert", N_("Insert from a PDF…")),
                ("replace", N_("Replace by pages of a PDF…")),
                (None, None), ("extract", N_("Extract to a new PDF…")), ("split", N_("Split…")))


class MainWindow(QMainWindow):
    def __init__(self, state: dict | None = None):
        """STATE (from export_state) carries the document over when the window is
        built again, for instance in another language."""
        super().__init__()
        self.setAcceptDrops(True)
        self.settings = QSettings("py-foliation", "py-foliation")
        self.path: Path | None = None
        self.count = 0  # (the pages there will be, once the operations on them waiting are made)
        self.file_count = 0  # (the pages of the file)
        self.ranges: list[Range] = []  # (normalized)
        self.saved: list[Range] = []  # the labels of the file
        self.opening = View()  # the view of the document when it is opened
        self.saved_opening = View()  # the one the file has
        # headers and footers, and watermarks, to add, update or remove when the file is saved (in order)
        self.hf_changes: tuple[Change, ...] = ()
        self.added: list[stamps.Addition] = []  # what the pages have, with those changes made
        # (ranges, view, header and footer changes) before each change
        self.undo_stack: list[tuple[list[Range], View, tuple]] = []
        self.redo_stack: list[tuple[list[Range], View, tuple]] = []
        self._previewed = None  # what the preview shows: the file, or a copy with the changes
        self._tmpdir: tempfile.TemporaryDirectory | None = None
        self.password = ""  # (of the open document)
        # The thumbnails drawn, by what each shows (see _page_keys), the latest seen last; they
        # outlive the changes that leave their pages as they are (labels, moves, deletions...).
        self._thumb_cache: OrderedDict = OrderedDict()
        self._keys: list = []  # what each page of the preview shows (its key in _thumb_cache)
        self._blank: QIcon | None = None
        self._syncing = False  # (while the list and the panel of thumbnails are made to agree)
        self._preview_source: Path | None = None  # (the file the preview shows)
        self._page_sizes: list[tuple[float, float]] = []  # (of its pages, for the thumbnails)
        self._previews = 0  # (copies made for the preview: each has a name of its own)
        self._building = False
        self._build()
        self._build_menus()
        self._build_page_actions()
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

        self.pages = PageList()
        self.pages.setToolTip(tr("Double-click a page to start a range at it; select pages (Shift, Ctrl) and "
                                 "right-click them for more; drag them to move them (with Ctrl, to copy them), "
                                 "or drop PDFs to insert their pages"))
        self.pages.moved.connect(self.move_pages)
        self.pages.files_dropped.connect(self.files_dropped)
        self.pages.currentRowChanged.connect(self._page_chosen)
        self.pages.itemDoubleClicked.connect(lambda item: self.start_range_at(self.pages.row(item) + 1))
        self.pages.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.pages.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pages.customContextMenuRequested.connect(self.pages_menu)
        self.renderer = ThumbRenderer(self)
        self.renderer.drawn.connect(self._thumb_drawn)
        self.thumb_timer = QTimer(self)  # (the thumbnails to draw, chosen once scrolling stops a moment)
        self.thumb_timer.setSingleShot(True)
        self.thumb_timer.setInterval(30)
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
        self.pages_title = QLabel("<b>" + tr("Pages and their labels") + "</b>")
        lay.addWidget(self.pages_title)
        lay.addWidget(self.pages, 3)
        lay.addWidget(QLabel(tr("Command line:")))
        lay.addWidget(self.cmd_line)

        self.doc = QPdfDocument(self)
        self.view = QPdfView(self)
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.SinglePage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitInView)
        # (a page fitted in the view needs no scroll bars, and with them left to Qt, at some sizes
        # showing one shrinks the page so that it isn't needed, hiding it makes it needed again,
        # and the window stops answering)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        height = int(self.settings.value("thumbnail_size", thumbnails.DEFAULT) or thumbnails.DEFAULT)
        self.thumbs = ThumbsPanel(self, max(thumbnails.SMALLEST, min(height, thumbnails.LARGEST)))
        self.thumbs.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
                                    | Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.thumbs)
        self.thumbs.hide()
        thumbs = self.thumbs.list
        thumbs.currentRowChanged.connect(self._thumb_chosen)
        thumbs.itemSelectionChanged.connect(lambda: self._mirror_selection(thumbs, self.pages))
        self.pages.itemSelectionChanged.connect(lambda: self._mirror_selection(self.pages, thumbs))
        thumbs.itemDoubleClicked.connect(lambda item: self.start_range_at(thumbs.row(item) + 1))
        thumbs.customContextMenuRequested.connect(lambda pos: self.pages_menu(pos, thumbs))
        thumbs.moved.connect(self.move_pages)
        thumbs.files_dropped.connect(self.files_dropped)
        self.thumbs.resized.connect(self._thumbs_resized)
        thumbs.verticalScrollBar().valueChanged.connect(lambda *_: self.thumb_timer.start())
        thumbs.horizontalScrollBar().valueChanged.connect(lambda *_: self.thumb_timer.start())
        thumbs.viewport().installEventFilter(self)
        self.thumbs.visibilityChanged.connect(self._thumbs_shown)

    def _build_page_actions(self):
        """The actions on the pages chosen that are always at hand: in the bar of the panel of
        thumbnails, and with their keys in it and in the list of pages."""
        def act(text, icon, symbol, keys, triggered):
            a = QAction(tr(text), self)
            themed = QIcon.fromTheme(icon)
            a.setIcon(themed if not themed.isNull() else thumbnails.symbol(symbol))
            if keys:
                a.setShortcuts([QKeySequence(k) for k in keys])
                a.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
                a.setToolTip(f"{tr(text)} ({QKeySequence(keys[0]).toString(QKeySequence.SequenceFormat.NativeText)})")
            a.triggered.connect(lambda *_: triggered(self.selected_pages()) if self.path and self.count else None)
            for where in (self.pages, self.thumbs.list):
                where.addAction(a)
            return a

        self.a_rotate_left = act(N_("Rotate 90° counterclockwise"), "object-rotate-left", "↺", ["Ctrl+Shift+R"],
                                 lambda pages: self.arrange_pages(arrange.Rotate(tuple(pages), 270)))
        self.a_rotate_right = act(N_("Rotate 90° clockwise"), "object-rotate-right", "↻", ["Ctrl+R"],
                                  lambda pages: self.arrange_pages(arrange.Rotate(tuple(pages), 90)))
        self.a_earlier = act(N_("Move one page earlier"), "go-previous", "◀", ["Alt+Left", "Alt+Up"],
                             lambda pages: pages[0] > 1 and self.move_pages(pages, pages[0] - 1))
        self.a_later = act(N_("Move one page later"), "go-next", "▶", ["Alt+Right", "Alt+Down"],
                           lambda pages: pages[-1] < self.count and self.move_pages(pages, pages[-1] + 2))
        self.a_duplicate = act(N_("Duplicate"), "edit-copy", "⧉", ["Ctrl+D"],
                               lambda pages: self.arrange_pages(arrange.Duplicate(tuple(pages))))
        self.a_delete = act(N_("Delete"), "edit-delete", "✕", ["Delete"],
                            lambda pages: len(pages) < self.count
                            and self.arrange_pages(arrange.Delete(tuple(pages))))
        self.a_blank = act(N_("Insert a blank page after these"), "document-new", "+", [],
                           lambda pages: self.arrange_pages(arrange.InsertBlank(pages[-1] + 1)))
        self.a_insert = act(N_("Insert pages of a PDF before these…"), "document-import", "⤓", [],
                            lambda pages: self.arrange_dialog("insert", pages))
        self.page_actions = [self.a_rotate_left, self.a_rotate_right, self.a_earlier, self.a_later,
                             self.a_duplicate, self.a_delete, self.a_blank, self.a_insert]
        self.m_more = QMenu(tr("More"), self)
        self.m_more.aboutToShow.connect(lambda: self._fill_more(self.m_more))
        self.thumbs.set_actions([self.a_rotate_left, self.a_rotate_right, None, self.a_earlier, self.a_later, None,
                                 self.a_duplicate, self.a_delete, None, self.a_blank, self.a_insert], self.m_more)
        for where in (self.pages, self.thumbs.list):
            where.itemSelectionChanged.connect(self._update_page_actions)
        self._update_page_actions()

    def _fill_more(self, menu: QMenu):
        """MENU: all the operations on the pages chosen, with their dialogs."""
        menu.clear()
        pages = self.selected_pages()
        for mode, text in ARRANGE_MENU:
            if mode is None:
                menu.addSeparator()
            else:
                menu.addAction(tr(text), lambda *_, md=mode: self.arrange_dialog(md, pages)).setEnabled(
                    self.path is not None)

    def _update_page_actions(self):
        """Which of the actions on the pages chosen can be done now."""
        pages = self.selected_pages() if self.path is not None else []
        for a in self.page_actions:
            a.setEnabled(bool(pages))
        if pages:
            self.a_earlier.setEnabled(pages[0] > 1)
            self.a_later.setEnabled(pages[-1] < self.count)
            self.a_delete.setEnabled(len(pages) < self.count)

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
        # Save as: a copy as a plain PDF (which then stays open), or, as an export, PDF/A or PDF/X
        self.m_output = m.addMenu(tr("Save as"))
        self.m_output.setToolTipsVisible(True)
        self.output_actions = {}
        for value, name in [("", N_("PDF"))] + conform.STANDARDS:
            if value:
                act = self._action(self.m_output, tr(name) + "…", lambda _=False, v=value: self.export_dialog_as(v))
            else:
                act = self._action(self.m_output, tr(name) + "…", self.save_as, "Ctrl+Shift+S",
                                   tr("Save a copy of the file with these page labels"))
            self.output_actions[value] = act
        self.a_save_as = self.output_actions[""]
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
        self.a_thumbs = QAction(tr("Thumbnails"), self, checkable=True, shortcut="F4")
        self.a_thumbs.setToolTip(tr("A panel with the pages as thumbnails, of the size you choose"))
        self.a_thumbs.toggled.connect(self.show_thumbnails)
        m.addAction(self.a_thumbs)
        self.a_page_list = QAction(tr("List of pages"), self, checkable=True, checked=True)
        self.a_page_list.setToolTip(tr("The list of the pages and their labels, under the ranges"))
        self.a_page_list.toggled.connect(self.show_page_list)
        m.addAction(self.a_page_list)
        self.m_view = m
        m.aboutToShow.connect(self._fill_view_menu)
        self._fill_view_menu()
        m = self.menuBar().addMenu(tr("&Pages"))
        self.arrange_actions = []
        for mode, text in ARRANGE_MENU:
            if mode is None:
                m.addSeparator()
                continue
            self.arrange_actions.append(self._action(m, tr(text), lambda *_, md=mode: self.arrange_dialog(md)))
        m.addSeparator()
        self.m_labels_rule = m.addMenu(tr("The labels, when pages move"))
        group = QActionGroup(self)
        rule = self.settings.value("labels_when_moving", "ask")
        for code, text in (("ask", N_("Ask each time")), (arrange.FOLLOW, arrange.LABEL_CHOICES[arrange.FOLLOW]),
                           (arrange.POSITION, arrange.LABEL_CHOICES[arrange.POSITION])):
            act = QAction(tr(text), self, checkable=True)
            act.setChecked(code == rule)
            act.setData(code)
            act.triggered.connect(lambda _=False, c=code: self.set_labels_rule(c))
            group.addAction(act)
            self.m_labels_rule.addAction(act)
        m.addSeparator()
        self.m_headfoot = m.addMenu(tr("Header and Footer"))
        self.m_headfoot.aboutToShow.connect(self._fill_headfoot_menu)
        self.m_headfoot.setToolTipsVisible(True)
        self._fill_headfoot_menu()
        self.m_watermark = m.addMenu(tr("Watermark"))
        self.m_watermark.aboutToShow.connect(self._fill_watermark_menu)
        self.m_watermark.setToolTipsVisible(True)
        self._fill_watermark_menu()
        m.addSeparator()
        self._action(m, tr("On several files…"), self.batch_dialog,
                     tip=tr("Add or remove headers and footers, Bates numbers or watermarks on several PDFs at "
                            "once, the Bates numbers going on from one file to the next"))
        m = self.menuBar().addMenu(tr("&Settings"))
        lang = m.addMenu(tr("Language"))
        group = QActionGroup(self)
        for code, name in interface.names().items():
            act = QAction(name, self, checkable=True)
            act.setChecked(code == interface.code())
            act.triggered.connect(lambda _=False, c=code: self.change_language(c))
            group.addAction(act)
            lang.addAction(act)
        self._action(m, tr("pdf2iso…"), self.pdfconform_dialog,
                     tip=tr("Where pdf2iso is, which makes PDF/A and PDF/X"))
        m.setToolTipsVisible(True)
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
        state = self.settings.value("window_state")
        if isinstance(state, QByteArray):
            self.restoreState(state)  # (where the panel of thumbnails was)
        else:  # (room for two columns of thumbnails, at first)
            self.resizeDocks([self.thumbs], [2 * thumbnails.grid(self.thumbs.height_of_thumbnails()).width() + 30],
                             Qt.Orientation.Horizontal)
        self.a_thumbs.setChecked(self.settings.value("thumbnails", "false") == "true")
        self.a_page_list.setChecked(self.settings.value("page_list", "true") == "true")
        self.thumbs.setVisible(self.a_thumbs.isChecked())

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("thumbnails", "true" if self.a_thumbs.isChecked() else "false")
        self.settings.setValue("thumbnail_size", self.thumbs.height_of_thumbnails())
        self.settings.setValue("page_list", "true" if self.a_page_list.isChecked() else "false")
        self.settings.setValue("window_state", self.saveState())
        self.settings.sync()

    def closeEvent(self, event):
        if not self.maybe_discard():
            event.ignore()
            return
        self.save_settings()
        self.renderer.stop()
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and obj is self.thumbs.list.viewport():
            self.thumb_timer.start()  # (other pages come into view)
        return super().eventFilter(obj, event)

    def export_state(self) -> dict:
        """What a new window needs to carry on with the same document."""
        return {"path": self.path, "ranges": self.ranges, "saved": self.saved, "opening": self.opening,
                "saved_opening": self.saved_opening, "hf_changes": self.hf_changes, "undo": self.undo_stack,
                "redo": self.redo_stack, "page": self.current_page(), "password": self.password}

    def adopt_state(self, state: dict):
        if state["path"] is None:
            return
        self.password = state.get("password", "")
        self._load(state["path"], state["saved"], state["saved_opening"])
        self.undo_stack, self.redo_stack = list(state["undo"]), list(state["redo"])
        self.ranges, self.opening = state["ranges"], state["opening"]
        self.hf_changes = state.get("hf_changes", ())
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
            QMessageBox.warning(self, tr("Language"),
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
        self.renderer.stop()
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
        saved, _, self.password, saved_opening = read
        self.settings.setValue("last_dir", str(path.parent))
        self.add_recent(path)
        self._load(path, saved, saved_opening)
        self.undo_stack, self.redo_stack = [], []
        self.ranges, self.opening, self.hf_changes = list(saved), saved_opening, ()
        self.refresh()
        self.show_page(1)
        self.status(tr("Opened {path}", path=path))
        return True

    def read_pdf(self, path: Path) -> tuple[list[Range], int, str, View] | None:
        """(the labels, the number of pages, the password, the view) of the PDF at
        PATH, asking for its password if it needs one; None if it can't be read."""
        password = ""
        while True:
            try:
                with pikepdf.open(path, password=password) as pdf:
                    return labels.read_labels(pdf), len(pdf.pages), password, read_view(pdf)
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

    def _load(self, path: Path, saved: list[Range], saved_opening: View):
        self.doc.close()
        self.doc.setPassword(self.password)
        self.doc.load(str(path))
        self.path = path
        self.saved = list(saved)
        self.saved_opening = saved_opening
        self._thumb_cache.clear()
        self._previewed = None
        with pikepdf.open(path, password=self.password) as pdf:
            self.count = self.file_count = len(pdf.pages)
            self.added = stamps.additions(pdf)

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
        self.path = target
        self._previewed = None
        self.add_recent(target)
        self.refresh()
        return True

    def _write(self, target: Path) -> bool:
        if target == self.path:  # (the preview keeps the file open: let it go)
            self.doc.close()
            self._previewed = None
        try:
            write_copy(self.path, self.ranges, target, self.password, self.opening, self.hf_changes)
        except (OSError, pikepdf.PdfError, LabelError) as e:
            self.status(tr("{path} cannot be written: {error}", path=target, error=e), error=True)
            self.refresh()
            return False
        if self.hf_changes:
            # (the changes waiting are now in the file: those of the history would be applied to it again)
            self.undo_stack.clear()
            self.redo_stack.clear()
        with pikepdf.open(target, password=self.password) as pdf:
            self.added = stamps.additions(pdf)
            self.file_count = len(pdf.pages)
        self.saved, self.saved_opening, self.hf_changes = list(self.ranges), self.opening, ()
        self._previewed = None
        if target == self.path:
            self._thumb_cache.clear()  # (the pages of the file are now others)
        if target == self.path:
            self.refresh()
        self.status(tr("Saved {path}", path=target))
        return True

    def export_dialog_as(self, standard: str) -> bool:
        """Save a copy with these page labels as STANDARD ('a-2b', 'x-4'...): an export, which
        leaves the file open as it was, with its changes still to save."""
        if self.path is None:
            return False
        title = tr("Save a copy as {standard}", standard=conform.label(standard))
        target = self._ask_save(title, f"{self.path.stem}-labelled.pdf")
        if target is None:
            return False
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        self.settings.setValue("last_dir", str(target.parent))
        return self.export_as(target, standard)

    def export_as(self, target: Path, standard: str) -> bool:
        """Write the file with these page labels as TARGET, made STANDARD by pdf2iso."""
        if target.resolve() == self.path.resolve():
            self.status(tr("A copy as {standard} can't take the place of the file open; choose another name",
                           standard=conform.label(standard)), error=True)
            return False
        if not conform.available():
            self.warn(conform.label(standard), tr("{standard} can't be made: {command} is not installed (or "
                                                  "not where Settings say)", standard=conform.label(standard),
                                                  command=conform.COMMAND))
            return False
        try:
            write_copy(self.path, self.ranges, target, self.password, self.opening, self.hf_changes)
        except (OSError, pikepdf.PdfError, LabelError) as e:
            self.status(tr("{path} cannot be written: {error}", path=target, error=e), error=True)
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.status(tr("Making {standard} with {command}…", standard=conform.label(standard),
                       command=conform.COMMAND))
        QApplication.processEvents()
        try:
            check = conform.convert(target, target, standard, self.password)
        except conform.ConformError as e:
            QApplication.restoreOverrideCursor()
            self.warn(conform.label(standard), tr("The copy was saved as a plain PDF, but it could not be made "
                                                  "{standard}:\n\n{error}", standard=conform.label(standard),
                                                  error=e))
            self.status(tr("Saved {path}", path=target))
            return False
        QApplication.restoreOverrideCursor()
        self.add_recent(target)
        message = tr("Saved {path}", path=target) + " — " + conform.label(standard) + (f" ({check})" if check else "")
        if self.password:
            message += " — " + tr("PDF/A and PDF/X can't be protected: the copy has no password")
        self.status(message)
        return True

    def pdfconform_dialog(self) -> bool:
        """Settings ▸ pdf2iso: where it is."""
        dlg = PdfconformDialog(config.get("pdfconform") or "", self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        return self.set_pdfconform(dlg.path())

    def set_pdfconform(self, path: str) -> bool:
        try:
            config.set("pdfconform", path)
        except OSError as e:
            self.status(tr("Could not keep the setting: {error}", error=e), error=True)
            return False
        self._show_output()
        return True

    def _show_output(self):
        """The Save as menu: PDF/A and PDF/X greyed out if pdf2iso isn't there."""
        have = conform.available()
        for value, act in self.output_actions.items():
            if value:
                act.setEnabled(self.path is not None and have)
                act.setToolTip("" if have else tr("Needs {command}: install it, or say where it is in Settings",
                                                  command=conform.COMMAND))

    def revert(self):
        if self.is_modified():
            self.change(list(self.saved), view=self.saved_opening, hf_changes=())

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
        ranges, count, _, _ = read  # (the labels only, not the view)
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

    def change(self, ranges: list[Range], select: int | None = None, view: View | None = None,
               hf_changes: tuple | None = None):
        """Make RANGES the labels, VIEW (if given) the view of the document and HF_CHANGES (if
        given) the headers and footers to add or remove, undoably; SELECT: the first page of the
        range to select."""
        ranges = labels.normalize(ranges)
        view = self.opening if view is None else view
        hf_changes = self.hf_changes if hf_changes is None else tuple(hf_changes)
        if (ranges, view, hf_changes) != (self.ranges, self.opening, self.hf_changes):
            self.undo_stack.append((self.ranges, self.opening, self.hf_changes))
            self.redo_stack.clear()
            self.ranges, self.opening, self.hf_changes = ranges, view, hf_changes
        self.refresh(select)

    # ----------------------------------------------------------------- headers and footers

    def pages_with(self, kind: str = stamps.HEADER_FOOTER, bates_only: bool = False) -> set[int]:
        """The pages that will have a layer of KIND (only with Bates numbers, if BATES_ONLY) once saved."""
        return {p for a in self.added if a.kind == kind and (a.bates or not bates_only) for p in a.pages}

    def pages_with_header_footer(self) -> set[int]:
        return self.pages_with(stamps.HEADER_FOOTER)

    def last_added(self, kind: str):
        """(addition, settings) of the last layer of KIND the pages will have (None if none)."""
        found = stamps.last_addition(self.added, kind)
        if found is None or not found.settings:
            return None
        cls = headfoot.HeaderFooter if kind == stamps.HEADER_FOOTER else watermark.Watermark
        try:
            return found.id, cls.from_dict(found.settings)
        except LabelError:
            return None

    def _start_settings(self, kind: str):
        """The settings a dialog of KIND starts with: those added last, or the defaults."""
        for c in reversed(self.hf_changes):
            if c.settings is not None and c.settings.KIND == kind:
                return c.settings
        last = self.last_added(kind)
        if last is not None:
            return last[1]
        return headfoot.HeaderFooter() if kind == stamps.HEADER_FOOTER else watermark.Watermark()

    def stamp_dialog(self, kind: str = stamps.HEADER_FOOTER, pages: list[int] | None = None,
                     update: bool = False) -> bool:
        """Ask for a header and footer, or a watermark (on PAGES, if given), and add it; with UPDATE,
        replace the last one added."""
        if self.path is None:
            return False
        replaces = None
        if update:
            last = self.last_added(kind)
            if last is None:
                self.status(tr("There is nothing to update"), error=True)
                return False
            replaces, settings = last
        else:
            settings = self._start_settings(kind)
        if pages is not None:
            settings = dataclasses.replace(settings, pages=stamps.compact_pages(pages), parity="all")
        answer = self.ask_stamp(kind, settings, pages[0] if pages else self.current_page(),
                                existing=bool(self.pages_with(kind)) and not update)
        if answer is None:
            return False
        settings, keep = answer
        return self.add_stamp(settings, keep, replaces)

    def header_footer_dialog(self, pages: list[int] | None = None) -> bool:
        return self.stamp_dialog(stamps.HEADER_FOOTER, pages)

    def ask_stamp(self, kind: str, settings, page: int, existing: bool = False):
        """(settings, keep) from the dialog of KIND (None if cancelled)."""
        ask = ask_header_footer if kind == stamps.HEADER_FOOTER else ask_watermark
        return ask(self, settings, self.path, self.password, labels.page_labels(self.ranges, self.count), page,
                   existing)

    def add_stamp(self, settings, keep: bool = False, replaces: int | None = None) -> bool:
        """Add SETTINGS (a header and footer, or a watermark) when the file is saved (undoably)."""
        if self.path is None:
            return False
        module = headfoot if settings.KIND == stamps.HEADER_FOOTER else watermark
        try:
            settings = module.check(settings)
            stamps.chosen_pages(settings, self.count)
        except LabelError as e:
            self.status(str(e), error=True)
            return False
        self.change(self.ranges, hf_changes=self.hf_changes + (Change(settings, keep=keep, replaces=replaces),))
        if settings.KIND == stamps.HEADER_FOOTER:
            self.status(tr("Header and footer added (they are written when the file is saved)"))
        else:
            self.status(tr("Watermark added (it is written when the file is saved)"))
        return True

    def add_header_footer(self, hf: headfoot.HeaderFooter, keep: bool = False) -> bool:
        return self.add_stamp(hf, keep)

    def remove_stamps(self, kind: str = stamps.HEADER_FOOTER, pages: list[int] | None = None,
                      bates_only: bool = False) -> bool:
        """Take away the layers of KIND py-foliation added (on PAGES, or all; only those with Bates
        numbers, if BATES_ONLY), when the file is saved."""
        if self.path is None or not self.pages_with(kind, bates_only):
            return False
        spec = stamps.compact_pages(pages) if pages else ""
        self.change(self.ranges, hf_changes=self.hf_changes + (Change(None, kind=kind, pages=spec,
                                                                       bates_only=bates_only),))
        self.status(tr("Taken away (when the file is saved)"))
        return True

    def remove_header_footer(self, pages: list[int] | None = None) -> bool:
        return self.remove_stamps(stamps.HEADER_FOOTER, pages)

    def apply_profile(self, name: str, kind: str = stamps.HEADER_FOOTER) -> bool:
        module = headfoot if kind == stamps.HEADER_FOOTER else watermark
        profile = module.read_profiles().get(name)
        return profile is not None and self.add_stamp(profile)

    def _fill_stamp_menu(self, m: QMenu, kind: str):
        m.clear()
        has = self.path is not None
        module = headfoot if kind == stamps.HEADER_FOOTER else watermark
        m.addAction(tr("Add…"), lambda *_: self.stamp_dialog(kind)).setEnabled(has)
        a = m.addAction(tr("Update…"), lambda *_: self.stamp_dialog(kind, update=True))
        a.setToolTip(tr("Change the settings of the last one added"))
        a.setEnabled(has and self.last_added(kind) is not None)
        a = m.addAction(tr("Remove all"), lambda *_: self.remove_stamps(kind))
        a.setToolTip(tr("Take away all those py-foliation added to this file"))
        a.setEnabled(has and bool(self.pages_with(kind)))
        if kind == stamps.HEADER_FOOTER:
            a = m.addAction(tr("Remove the Bates numbers"), lambda *_: self.remove_stamps(kind, bates_only=True))
            a.setToolTip(tr("Take away only the headers and footers with Bates numbers"))
            a.setEnabled(has and bool(self.pages_with(kind, bates_only=True)))
        shown = [p for p in module.read_profiles().values() if p.show_on_menu]
        if shown:
            m.addSection(tr("Profiles"))
            for p in shown:
                a = m.addAction(p.name, lambda *_, n=p.name: self.apply_profile(n, kind))
                a.setEnabled(has)

    def _fill_headfoot_menu(self):
        self._fill_stamp_menu(self.m_headfoot, stamps.HEADER_FOOTER)

    def _fill_watermark_menu(self):
        self._fill_stamp_menu(self.m_watermark, stamps.WATERMARK)

    # ----------------------------------------------------------------- arranging the pages

    def set_labels_rule(self, rule: str):
        """What the labels do when pages move: 'ask', arrange.FOLLOW or arrange.POSITION."""
        self.settings.setValue("labels_when_moving", rule)
        for act in self.m_labels_rule.actions():
            act.setChecked(act.data() == rule)

    def ask_labels(self):
        """(arrange.FOLLOW or POSITION, from now on?) as the user chooses (None if cancelled)."""
        return ask_labels(self)

    def labels_choice(self) -> str | None:
        """What the labels do when pages move: as Pages ▸ The labels says, or as the user says now."""
        rule = self.settings.value("labels_when_moving", "ask")
        if rule in (arrange.FOLLOW, arrange.POSITION):
            return rule
        answer = self.ask_labels()
        if answer is None:
            return None
        choice, keep = answer
        if keep:
            self.set_labels_rule(choice)
        return choice

    def arrange_pages(self, op: arrange.Operation, ask: bool = True) -> bool:
        """Make OP on the pages when the file is saved (undoably); with ASK, ask (if the pages move
        and have labels) what their labels do."""
        if self.path is None:
            return False
        try:
            if op.moves_pages():
                op.items(self.count)
            if ask and op.moves_pages() and self.ranges:
                choice = self.labels_choice()
                if choice is None:
                    return False
                op = dataclasses.replace(op, labels=choice)
            ranges = arrange.ranges_after(op, self.ranges, self.count)
            opening = self.opening
            if opening.page is not None:
                opening = dataclasses.replace(opening, page=arrange.position_after(op, opening.page, self.count))
        except LabelError as e:
            self.status(str(e), error=True)
            return False
        self.change(ranges, view=opening, hf_changes=self.hf_changes + (op,))
        self.status(op.describe() + " " + tr("(written when the file is saved)"))
        return True

    def move_pages(self, pages: list[int], before: int, copied: bool = False) -> bool:
        """Move PAGES before page BEFORE (count + 1: to the end); COPIED: copy them there."""
        if not pages:
            return False
        op = arrange.Duplicate(tuple(pages), before) if copied else arrange.Move(tuple(pages), before)
        if not copied and op.items(self.count) == list(range(1, self.count + 1)):
            return False  # (dropped where they were)
        n = self.count
        if not self.arrange_pages(op):
            return False
        items = op.items(n)
        first = next(i for i, item in enumerate(items) if item == pages[0] and (not copied or i + 1 != pages[0]))
        self.show_page(first + 1)
        if not copied and len(pages) > 1:  # (they stay chosen, to be moved again)
            moved = set(pages)
            self.pages.clearSelection()
            for i, item in enumerate(items):
                if isinstance(item, int) and item in moved:
                    self.pages.item(i).setSelected(True)
        return True

    def files_dropped(self, paths: list[Path], before: int) -> bool:
        """PDFs dropped on the list of pages: their pages inserted there (or, with no file open, open it)."""
        if self.path is None:
            return self.open_path(paths[0])
        choice = arrange.FOLLOW
        if self.ranges:
            choice = self.labels_choice()
            if choice is None:
                return False
        done = False
        for path in paths:
            try:
                count = arrange.source_count(str(path))
            except LabelError as e:
                self.status(str(e), error=True)
                continue
            done = self.arrange_pages(arrange.Insert(str(path), (), before, labels=choice), ask=False) or done
            before += count
        return done

    def ask_arrange(self, mode: str, pages: list[int] | None = None):
        return ask_arrange(self, mode, self.count, pages, self.current_page(), Path(self.last_dir()))

    def arrange_dialog(self, mode: str, pages: list[int] | None = None) -> bool:
        """The dialog of an operation on the pages (see arrange_dialog.MODES), and the operation."""
        if self.path is None:
            return False
        value = self.ask_arrange(mode, pages)
        if value is None:
            return False
        if mode == "extract":
            target = self._ask_save(tr("Extract to a new PDF"), f"{self.path.stem}-{stamps.compact_pages(value)}.pdf")
            return target is not None and self.write_parts([(target.with_suffix(".pdf"), value)])
        if mode == "split":
            parts, folder = value
            return self.write_parts([(folder / f"{self.path.stem}-{k}.pdf", list(range(first, last + 1)))
                                     for k, (first, last) in enumerate(parts, 1)])
        return self.arrange_pages(value, ask=False)

    def write_parts(self, parts: list[tuple[Path, list[int]]]) -> bool:
        """Save some pages, as they are now (with the changes waiting), as new files: [(target, pages)]."""
        try:
            files.write_parts(self.path, self.ranges, parts, self.password, self.opening, self.hf_changes)
        except (OSError, pikepdf.PdfError, LabelError) as e:
            self.status(tr("{path} cannot be written: {error}", path=parts[0][0], error=e), error=True)
            return False
        self.status(ntr("Saved {count} file: {path}", "Saved {count} files: {path}", len(parts), path=parts[0][0]))
        return True

    def batch_dialog(self) -> bool:
        """Headers and footers, Bates numbers or watermarks on several files at once."""
        from .batch_dialog import BatchDialog
        dlg = BatchDialog(self, [self.path] if self.path else [], Path(self.last_dir()))
        dlg.exec()
        return bool(dlg.written)

    def _update_preview(self):
        """Show in the preview the file, or a copy of it with the headers and footers waiting."""
        if self.path is None:
            return
        key = (self.path, self.hf_changes, tuple(self.ranges) if self._labels_shown() else None)
        if key == self._previewed:
            return
        source = self.path
        if self.hf_changes:
            if self._tmpdir is None:
                self._tmpdir = tempfile.TemporaryDirectory(prefix="py-foliation-")
            # (a new name each time: the thumbnails may still be drawn from the one before)
            self._previews += 1
            source = Path(self._tmpdir.name) / f"preview-{self._previews}.pdf"
            self.doc.close()
            try:
                write_copy(self.path, self.ranges, source, self.password, None, self.hf_changes)
            except (OSError, pikepdf.PdfError, LabelError) as e:
                self.status(str(e), error=True)
                source = self.path
        page = self.current_page()
        self.doc.close()
        self.doc.load(str(source))
        try:
            with pikepdf.open(source, password=self.password) as pdf:
                self.added = stamps.additions(pdf)
                self._page_sizes = thumbnails.page_sizes(pdf)
        except (OSError, pikepdf.PdfError):
            self._page_sizes = []
        old = self._preview_source
        self._preview_source = source
        self._previewed = key
        if old is not None and old != source and old.parent == Path(self._tmpdir.name if self._tmpdir else "/-"):
            old.unlink(missing_ok=True)
        if self.count:
            self._page_chosen(min(page, self.count) - 1)

    def _labels_shown(self) -> bool:
        """Whether a header, footer or watermark waiting shows page labels (so that the preview
        changes with them)."""
        return any("pagelabel" in repr(c) for c in self.hf_changes if not isinstance(c, arrange.Operation))

    def _page_keys(self) -> list:
        """What each page of the preview shows, as a key that stays the same as long as the page
        looks the same: the page of the file it comes from and its rotation, or the page inserted,
        stamped by the headers, footers and watermarks waiting (these with its place and, if they
        show them, the labels)."""
        keys = [(page, 0) for page in range(1, self.file_count + 1)]
        labels_now = tuple(self.ranges) if self._labels_shown() else None
        for change in self.hf_changes:
            if isinstance(change, arrange.Rotate):
                for page in change.pages:
                    if 0 < page <= len(keys):
                        shown, angle = keys[page - 1]
                        keys[page - 1] = (shown, (angle + change.angle) % 360)
            elif isinstance(change, arrange.Operation) and change.moves_pages():
                try:
                    items = change.items(len(keys))
                except LabelError:
                    break
                keys = [keys[item - 1] if isinstance(item, int) else ((repr(change), k), 0)
                        for k, item in enumerate(items)]
            elif isinstance(change, arrange.Operation):  # (a page replaced...)
                for page in getattr(change, "pages", ()):
                    if 0 < page <= len(keys):
                        keys[page - 1] = ((repr(change), page), 0)
            else:  # (a header, footer or watermark, which may differ from page to page)
                keys = [((repr(change), place, key, labels_now), 0) for place, key in enumerate(keys, 1)]
        return keys

    def set_view(self, new: View) -> None:
        """Make NEW the view of the document when it is opened (undoably)."""
        if self.path is not None:
            self.change(self.ranges, view=new)

    def set_view_part(self, field: str, value) -> None:
        """Change one part of the view when the document is opened: its layout, zoom (page view) or page."""
        new = dataclasses.replace(self.opening, **{field: value})
        self.set_view(view.without_lone_first_page(self.opening, new, page_given=field == "page"))

    def add_view_menus(self, menu: QMenu, page: int | None = None) -> None:
        """The submenus of MENU that choose the page layout and the page view of the document when
        it is opened (for the whole document: PDF has no other way), and with PAGE, the page it opens at."""
        menu.addSection(tr("When the document is opened"))
        for title, field, current, titles, tips in (
                (tr("Page layout"), "layout", self.opening.layout, view.LAYOUT_TITLES, view.LAYOUT_TIPS),
                (tr("Page view"), "zoom", self.opening.zoom, view.PAGE_VIEW_TITLES, view.PAGE_VIEW_TIPS)):
            sub = menu.addMenu(title)
            sub.setEnabled(self.path is not None)
            sub.setToolTipsVisible(True)
            group = QActionGroup(sub)
            choices = [("", tr("The viewer's choice"), "")]
            choices += [(code, tr(text), tr(tips[code])) for code, text in titles.items()]
            if current and current not in titles:  # (a page view of the file that isn't offered)
                choices.append((current, view.page_view_title(current), ""))
            for code, text, tip in choices:
                a = sub.addAction(text, lambda *_, f=field, c=code: self.set_view_part(f, c))
                a.setCheckable(True)
                a.setChecked(code == current)
                a.setToolTip(tip)
                group.addAction(a)
        if page is not None:
            a = menu.addAction(tr("Open the document at page {page}", page=page),
                               lambda *_: self.set_view_part("page", page))
            a.setToolTip(tr("Viewers will show this page first when they open the file"))
            a.setCheckable(True)
            a.setChecked(self.opening.page == page)
        menu.setToolTipsVisible(True)

    def _fill_view_menu(self):
        """The View menu, with the view of the document when it is opened as it is now."""
        self.m_view.clear()
        self.m_view.addAction(self.a_thumbs)
        self.m_view.addAction(self.a_page_list)
        self.add_view_menus(self.m_view)

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

    def pages_menu(self, pos, where=None):
        """The menu of the pages chosen, at POS in WHERE (the list of pages, or the thumbnails)."""
        if self.path is None:
            return
        where = where or self.pages
        item = where.itemAt(pos)
        if item is not None and not item.isSelected():
            where.setCurrentItem(item)
            if where is not self.pages:
                self.pages.setCurrentRow(where.row(item))
        menu = self.build_pages_menu()
        if menu is not None:
            menu.exec(where.viewport().mapToGlobal(pos))

    def build_pages_menu(self) -> QMenu | None:
        """The menu of actions on the chosen pages."""
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
        menu.addSection(tr("Pages"))
        menu.addAction(tr("Move to the start"), lambda *_: self.move_pages(pages, 1)).setEnabled(pages[0] > 1)
        menu.addAction(tr("Move to the end"), lambda *_: self.move_pages(pages, self.count + 1)).setEnabled(
            pages[-1] < self.count)
        menu.addAction(tr("Move before page…"), lambda *_: self.arrange_dialog("move", pages))
        turn = menu.addMenu(tr("Rotate"))
        for angle, text in ((90, N_("90° clockwise")), (270, N_("90° counterclockwise")), (180, N_("180°"))):
            turn.addAction(tr(text), lambda *_, a=angle: self.arrange_pages(arrange.Rotate(tuple(pages), a)))
        menu.addAction(tr("Duplicate"), lambda *_: self.arrange_pages(arrange.Duplicate(tuple(pages))))
        if count > 1:
            menu.addAction(tr("Reverse their order"), lambda *_: self.arrange_pages(arrange.Reverse(tuple(pages))))
        menu.addAction(tr("Delete"), lambda *_: self.arrange_pages(arrange.Delete(tuple(pages)))).setEnabled(
            count < self.count)
        menu.addAction(tr("Insert a blank page before this one") if count == 1 else
                       tr("Insert a blank page before these"),
                       lambda *_: self.arrange_pages(arrange.InsertBlank(pages[0])))
        menu.addAction(tr("Insert a blank page after this one") if count == 1 else
                       tr("Insert a blank page after these"),
                       lambda *_: self.arrange_pages(arrange.InsertBlank(pages[-1] + 1)))
        menu.addAction(tr("Insert blank pages…"), lambda *_: self.arrange_dialog("blank", pages))
        menu.addAction(tr("Insert pages of a PDF before this one…") if count == 1 else
                       tr("Insert pages of a PDF before these…"),
                       lambda *_: self.arrange_dialog("insert", pages))
        menu.addAction(tr("Replace by pages of a PDF…"), lambda *_: self.arrange_dialog("replace", pages))
        menu.addAction(tr("Extract to a new PDF…"), lambda *_: self.arrange_dialog("extract", pages))
        self._fill_more(menu.addMenu(tr("More")))
        menu.addSection(tr("Header, footer and watermark"))
        menu.addAction(tr("Header and footer on these pages…") if count > 1 else tr("Header and footer on this page…"),
                       lambda *_: self.stamp_dialog(stamps.HEADER_FOOTER, pages))
        menu.addAction(tr("Watermark on these pages…") if count > 1 else tr("Watermark on this page…"),
                       lambda *_: self.stamp_dialog(stamps.WATERMARK, pages))
        a = menu.addAction(tr("Remove their header and footer") if count > 1 else tr("Remove its header and footer"),
                           lambda *_: self.remove_stamps(stamps.HEADER_FOOTER, pages))
        a.setEnabled(bool(self.pages_with(stamps.HEADER_FOOTER) & set(pages)))
        a = menu.addAction(tr("Remove their watermark") if count > 1 else tr("Remove its watermark"),
                           lambda *_: self.remove_stamps(stamps.WATERMARK, pages))
        a.setEnabled(bool(self.pages_with(stamps.WATERMARK) & set(pages)))
        self.add_view_menus(menu, pages[0])
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
            self.redo_stack.append((self.ranges, self.opening, self.hf_changes))
            self.ranges, self.opening, self.hf_changes = self.undo_stack.pop()
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append((self.ranges, self.opening, self.hf_changes))
            self.ranges, self.opening, self.hf_changes = self.redo_stack.pop()
            self.refresh()

    # ----------------------------------------------------------------- showing

    def _recount(self):
        """The pages there will be, once the operations on them waiting are made."""
        operations = [c for c in self.hf_changes if isinstance(c, arrange.Operation)]
        try:
            self.count = arrange.items_of(operations, self.file_count)[1]
        except LabelError:
            self.count = self.file_count

    def refresh(self, select: int | None = None):
        """Show the ranges, the labels of the pages and the command line."""
        self._recount()
        if select is None:
            row = self.table.currentRow()
            select = self.ranges[row].page if 0 <= row < len(self.ranges) else None
        self._fill_table(select)
        self._update_preview()
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
        """The list of pages with their labels (and the panel of thumbnails, if it is shown), keeping
        the page shown and the pages chosen."""
        page = self.current_page()
        chosen = self.selected_pages()
        self.pages.blockSignals(True)
        self.pages.clear()
        for i, label in enumerate(labels.page_labels(self.ranges, self.count), 1):
            item = QListWidgetItem(f"{i:>5}   {label}")
            item.setToolTip(tr("page {page} of the file: {label}", page=i, label=label or tr("(no label)")))
            self.pages.addItem(item)
        self.pages.blockSignals(False)
        if self.count:
            self.pages.setCurrentRow(min(page, self.count) - 1)
            if len(chosen) > 1:  # (the pages chosen stay chosen, for another action on them)
                for p in chosen:
                    if p <= self.count:
                        self.pages.item(p - 1).setSelected(True)
        self._update_page_actions()
        self._fill_thumbs()

    def _fill_thumbs(self):
        """The panel of thumbnails, as the list of pages is (if it is shown)."""
        thumbs = self.thumbs.list
        if not self.a_thumbs.isChecked():
            self.thumb_timer.stop()
            self.renderer.set_jobs([])
            return
        self._keys = self._page_keys()
        height = self.thumbs.height_of_thumbnails()
        self._syncing = True
        thumbs.setUpdatesEnabled(False)
        thumbs.clear()
        for i, label in enumerate(labels.page_labels(self.ranges, self.count), 1):
            item = QListWidgetItem(str(i) if label == str(i) else f"{i}\n{label or '—'}")
            item.setToolTip(tr("page {page} of the file: {label}", page=i, label=label or tr("(no label)")))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            icon = self._thumb_cache.get((self._key(i), height))
            item.setIcon(icon or self._blank_thumb())
            thumbs.addItem(item)
        if self.count:
            thumbs.setCurrentRow(self.current_page() - 1, QItemSelectionModel.SelectionFlag.NoUpdate)
            self._select_rows(thumbs, [p - 1 for p in self.selected_pages()])
        thumbs.setUpdatesEnabled(True)
        self._syncing = False
        self.thumb_timer.start()

    def _key(self, page: int):
        return self._keys[page - 1] if 0 < page <= len(self._keys) else None

    def show_page_list(self, on: bool):
        """Show or hide the list of pages and their labels (the ranges take its room)."""
        self.pages_title.setVisible(on)
        self.pages.setVisible(on)

    def show_thumbnails(self, on: bool):
        """Show or hide the panel of thumbnails."""
        if self.thumbs.isVisible() != on:
            self.thumbs.setVisible(on)
        if not on:
            self.thumb_timer.stop()
        self._fill_thumbs()

    def _thumbs_shown(self, shown: bool):
        """The panel was shown or hidden (also by its own close button)."""
        if self.a_thumbs.isChecked() != shown and not self.isMinimized():
            self.a_thumbs.setChecked(shown)

    def _thumbs_resized(self, height: int):
        """New size of the thumbnails: drawn again (in the background)."""
        self._thumb_cache.clear()
        self._blank = None
        blank = self._blank_thumb()
        thumbs = self.thumbs.list
        for i in range(thumbs.count()):
            thumbs.item(i).setIcon(blank)
        if self.a_thumbs.isChecked():
            self.thumb_timer.start()

    def _thumb_chosen(self, row: int):
        if not self._syncing and row >= 0:  # (the pages chosen are already the same in both)
            self.pages.setCurrentRow(row, QItemSelectionModel.SelectionFlag.NoUpdate)

    def _mirror_selection(self, source, target):
        """Make TARGET (the list or the thumbnails) choose the pages SOURCE has chosen."""
        if self._syncing or target.count() != source.count():
            return
        self._syncing = True
        target.blockSignals(True)
        self._select_rows(target, sorted(source.row(i) for i in source.selectedItems()))
        if source.currentRow() >= 0:  # (the current page too, leaving the choice as it is)
            target.setCurrentRow(source.currentRow(), QItemSelectionModel.SelectionFlag.NoUpdate)
        target.blockSignals(False)
        self._syncing = False

    @staticmethod
    def _select_rows(view, rows: list[int]):
        """Choose ROWS (in order) of VIEW, and no others, at once (one by one is slow in a long book)."""
        model = view.model()
        selection = QItemSelection()
        start = prev = None
        for row in rows + [None]:
            if row is not None and prev is not None and row == prev + 1:
                prev = row
                continue
            if start is not None:
                selection.select(model.index(start, 0), model.index(prev, 0))
            start = prev = row
        view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    def _blank_thumb(self) -> QIcon:
        if self._blank is None:
            self._blank = thumbnails.blank(self.thumbs.height_of_thumbnails(), self.devicePixelRatioF())
        return self._blank

    def _cache_size(self) -> int:
        """How many thumbnails are kept (about 256 MB of them)."""
        each = thumbnails.nbytes(self.thumbs.height_of_thumbnails(), self.devicePixelRatioF())
        return max(64, (256 << 20) // max(each, 1))

    def _draw_thumbnails(self):
        """Ask for the thumbnails missing: those in view first, then those nearest to them, as many
        as are kept."""
        thumbs = self.thumbs.list
        if not self.a_thumbs.isChecked() or self.path is None or not self.count or self._preview_source is None:
            self.renderer.set_jobs([])
            return
        height, ratio = self.thumbs.height_of_thumbnails(), self.devicePixelRatioF()
        n = thumbs.count()
        first = thumbs.indexAt(thumbs.viewport().rect().topLeft() + QPoint(4, 4)).row()
        last = thumbs.indexAt(thumbs.viewport().rect().bottomRight() - QPoint(4, 4)).row()
        first = 0 if first < 0 else first
        if last < 0:  # (the end of the list is in view, or nothing is)
            last = n - 1
        while last + 1 < n and thumbs.visualItemRect(thumbs.item(last + 1)).intersects(thumbs.viewport().rect()):
            last += 1
        order = list(range(first, last + 1))
        before, after = first - 1, last + 1
        while before >= 0 or after < n:  # (then outwards from them, after before before)
            if after < n:
                order.append(after)
                after += 1
            if before >= 0:
                order.append(before)
                before -= 1
        jobs, asked = [], set()
        for row in order[:self._cache_size()]:
            key = (self._key(row + 1), height)
            if key[0] is None:
                continue
            if key in self._thumb_cache:
                self._thumb_cache.move_to_end(key)
            elif key not in asked:
                asked.add(key)
                size = self._page_sizes[row] if row < len(self._page_sizes) else None
                jobs.append(Job(str(self._preview_source), self.password or "", row + 1, height, ratio, key, size))
        self.renderer.set_jobs(jobs)

    def _thumb_drawn(self, key, height: int, image):
        """A thumbnail drawn: kept, and shown on the pages that show it."""
        if height != self.thumbs.height_of_thumbnails():
            return
        icon = thumbnails.frame(image, height, self.devicePixelRatioF())
        self._thumb_cache[key] = icon
        while len(self._thumb_cache) > self._cache_size():
            self._thumb_cache.popitem(last=False)
        thumbs = self.thumbs.list
        for row, shown in enumerate(self._keys):
            if (shown, height) == key and row < thumbs.count():
                thumbs.item(row).setIcon(icon)

    def thumbnails_pending(self) -> int:
        """The thumbnails still to be drawn (for the tests)."""
        return self.renderer.pending() + self.thumb_timer.isActive()

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
        """The page shown (1-based; within the pages there are, while the list catches up with them)."""
        row = self.pages.currentRow()
        page = row + 1 if row >= 0 else 1
        return max(1, min(page, self.count)) if self.count else page

    def show_page(self, page: int):
        if self.count:
            self.pages.setCurrentRow(max(1, min(page, self.count)) - 1)

    def _page_chosen(self, row: int):
        if row < 0 or not self.count:
            return
        if self.a_thumbs.isChecked() and not self._syncing and 0 <= row < self.thumbs.list.count():
            self._syncing = True
            self.thumbs.list.setCurrentRow(row, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.thumbs.list.scrollToItem(self.thumbs.list.item(row))
            self._syncing = False
            self._mirror_selection(self.pages, self.thumbs.list)
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
                  self.a_copy_from, self.a_import, self.a_export, self.go_to, *self.arrange_actions):
            w.setEnabled(has)
        self._show_output()
        self.a_undo.setEnabled(bool(self.undo_stack))
        self.a_redo.setEnabled(bool(self.redo_stack))

    # ----------------------------------------------------------------- unsaved changes

    def is_modified(self) -> bool:
        return self.path is not None and ((self.ranges, self.opening) != (self.saved, self.saved_opening)
                                          or bool(self.hf_changes))

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

    def warn(self, title: str, text: str):
        """A warning the user must see (a modal message box)."""
        QMessageBox.warning(self, title, text)

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


class PdfconformDialog(QDialog):
    """Where pdf2iso is: a file, or nothing to look for it (see conform.find)."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("pdf2iso"))
        self.edit = QLineEdit(path)
        self.edit.setPlaceholderText(tr("Look for it on the PATH, in ~/bin and in ~/.local/bin"))
        self.edit.setToolTip(tr("The script pdf2iso, which makes PDF/A and PDF/X (with or without "
                                "the .py extension); empty to look for it"))
        self.edit.setMinimumWidth(420)
        self.edit.textChanged.connect(self._show_found)
        choose = QPushButton(tr("Choose…"))
        choose.clicked.connect(self._choose)
        self.found = QLabel()
        self.found.setWordWrap(True)
        self.found.setStyleSheet("color: palette(placeholder-text);")
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("pdf2iso:")))
        row.addWidget(self.edit, 1)
        row.addWidget(choose)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.found)
        lay.addWidget(buttons)
        self._show_found()

    def path(self) -> str:
        return self.edit.text().strip()

    def _show_found(self, *_):
        """Which pdf2iso will be used (File ▸ Save as ▸ PDF/A, PDF/X)."""
        path = self.path()
        found = conform.find(path)
        if found is not None:
            self.found.setText(tr("It will be {path}", path=found))
        elif path:
            self.found.setText(tr("There is no such file"))
        else:
            self.found.setText(tr("Not found: PDF/A and PDF/X can't be made until it is given here"))

    def _choose(self):
        start = self.path() or str(Path.home() / "bin")
        name, _ = QFileDialog.getOpenFileName(self, tr("Where is pdf2iso?"), start,
                                              tr("pdf2iso (pdf2iso pdf2iso.py);;All files (*)"))
        if name:
            self.edit.setText(name)
