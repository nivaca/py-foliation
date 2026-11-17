"""The dialog of headers and footers: what to write in each place, the margins, the
appearance, the pages and Bates numbering, with a preview of a page and the profiles kept."""

from __future__ import annotations

import dataclasses
import io
from datetime import datetime
from pathlib import Path

import pikepdf
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QRadioButton,
    QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from .. import headfoot
from ..headfoot import HeaderFooter
from ..interface import tr
from ..labels import LabelError

PREVIEW = QSize(300, 390)  # the largest preview of a page


class ColorButton(QPushButton):
    """A button that shows a color and lets the user choose another."""

    def __init__(self, color: str = "#000000"):
        super().__init__()
        self.setFixedWidth(56)
        self.clicked.connect(self._choose)
        self.color = ""
        self.set_color(color)

    def set_color(self, color: str):
        self.color = color or "#000000"
        swatch = QPixmap(28, 14)
        swatch.fill(QColor(self.color))
        self.setIcon(QIcon(swatch))
        self.setIconSize(swatch.size())
        self.setToolTip(self.color)

    def _choose(self):
        chosen = QColorDialog.getColor(QColor(self.color), self, tr("Color"))
        if chosen.isValid():
            self.set_color(chosen.name())
            self.colorChanged()

    def colorChanged(self):  # (replaced by the dialog)
        pass


class SlotEdit(QLineEdit):
    """The text of one place; the dialog inserts variables into the last one that had the focus."""

    def __init__(self, dialog: HeaderFooterDialog, slot: str):
        super().__init__()
        self.dialog, self.slot = dialog, slot

    def focusInEvent(self, event):
        self.dialog.target = self
        super().focusInEvent(event)


class HeaderFooterDialog(QDialog):
    """Settings for a header and footer, from HF; the pages it goes on and its texts are checked
    against the document at SOURCE (with its pages labelled LABELS), whose page PAGE is previewed."""

    def __init__(self, parent, hf: HeaderFooter, source: Path, password: str, labels: list[str], page: int = 1):
        super().__init__(parent)
        self.setWindowTitle(tr("Header and Footer"))
        self.pdf = pikepdf.open(source, password=password)
        self.doc = headfoot.document_of(self.pdf, source, labels)
        self.now = datetime.now()
        self._loading = False
        self._buffer: QBuffer | None = None
        self.preview_doc = QPdfDocument(self)
        self.timer = QTimer(self, singleShot=True, interval=150)
        self.timer.timeout.connect(self.update_preview)

        # ------------------------------------------------- profile
        self.profile = QComboBox()
        self.profile.setMinimumWidth(180)
        self.show_on_menu = QCheckBox(tr("Show on menu"))
        self.show_on_menu.setToolTip(tr("List this profile in the Header and Footer menu, to apply it at once"))
        save = QPushButton(tr("Save…"))
        save.setToolTip(tr("Keep these settings as a profile"))
        save.clicked.connect(self.save_profile)
        self.delete = QPushButton(tr("Delete"))
        self.delete.clicked.connect(self.delete_profile)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("Profile:")))
        top.addWidget(self.profile, 1)
        top.addWidget(self.show_on_menu)
        top.addWidget(save)
        top.addWidget(self.delete)

        # ------------------------------------------------- the texts
        self.slots: dict[str, SlotEdit] = {}
        texts = QGridLayout()
        for row, prefix in enumerate(("header", "footer")):
            for col, side in enumerate(("left", "center", "right")):
                slot = f"{prefix}_{side}"
                edit = SlotEdit(self, slot)
                edit.setPlaceholderText(tr(headfoot.SLOT_TITLES[slot]))
                edit.setToolTip(tr(headfoot.SLOT_TITLES[slot]))
                edit.textChanged.connect(self.changed)
                self.slots[slot] = edit
                texts.addWidget(edit, row, col)
        self.target: SlotEdit = self.slots["footer_center"]
        insert = QHBoxLayout()
        insert.addWidget(QLabel(tr("Insert:")))
        for text, variable in ((tr("Date"), "date"), (tr("Page number"), "page"), (tr("Page label"), "pagelabel"),
                               (tr("Bates number"), "bates")):
            b = QPushButton(text)
            b.setToolTip(f"${variable}: {tr(headfoot.VARIABLES[variable])}")
            b.clicked.connect(lambda *_, v=variable: self.insert(v))
            insert.addWidget(b)
        other = QToolButton()
        other.setText(tr("Other"))
        other.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(other)
        for variable, help_text in headfoot.VARIABLES.items():
            menu.addAction(f"${variable}  —  {tr(help_text)}", lambda *_, v=variable: self.insert(v))
        other.setMenu(menu)
        insert.addWidget(other)
        insert.addStretch(1)
        texts_box = QGroupBox(tr("Header and footer"))
        lay = QVBoxLayout(texts_box)
        lay.addLayout(texts)
        lay.addLayout(insert)

        # ------------------------------------------------- margins
        self.units = QComboBox()
        for code, title in headfoot.UNIT_TITLES.items():
            self.units.addItem(tr(title), code)
        self.units.currentIndexChanged.connect(self._units_changed)
        self.margins = {}
        margins = QFormLayout()
        margins.addRow(tr("Units"), self.units)
        for side, title in (("top", tr("Top")), ("bottom", tr("Bottom")), ("left", tr("Left")),
                            ("right", tr("Right"))):
            spin = QDoubleSpinBox()
            spin.setRange(0, 1000)
            spin.setDecimals(2)
            spin.valueChanged.connect(self.changed)
            self.margins[side] = spin
            margins.addRow(title, spin)
        self.shrink = QCheckBox(tr("Shrink the pages"))
        self.shrink.setToolTip(tr("Scale the content of the pages down so that the header and footer don't "
                                  "cover it"))
        self.shrink.toggled.connect(self.changed)
        margins.addRow(self.shrink)
        margins_box = QGroupBox(tr("Margins"))
        margins_box.setLayout(margins)

        # ------------------------------------------------- appearance
        self.font_box = QComboBox()
        for code, title in headfoot.FAMILY_TITLES.items():
            self.font_box.addItem(title, code)
        self.font_box.currentIndexChanged.connect(self.changed)
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(1, 200)
        self.font_size.setDecimals(1)
        self.font_size.setSuffix(" pt")
        self.font_size.valueChanged.connect(self.changed)
        self.color = ColorButton()
        self.color.colorChanged = self.changed
        self.bold = QCheckBox(tr("Bold"))
        self.italic = QCheckBox(tr("Italic"))
        for box in (self.bold, self.italic):
            box.toggled.connect(self.changed)
        font_row = QHBoxLayout()
        for w in (self.font_box, self.font_size, self.color, self.bold, self.italic):
            font_row.addWidget(w)
        self.border = QCheckBox(tr("Border"))
        self.border.toggled.connect(self.changed)
        self.border_color = ColorButton()
        self.border_color.colorChanged = self.changed
        self.border_width = QDoubleSpinBox()
        self.border_width.setRange(0, 20)
        self.border_width.setDecimals(2)
        self.border_width.setSuffix(" pt")
        self.border_width.valueChanged.connect(self.changed)
        border_row = QHBoxLayout()
        for w in (self.border, self.border_color, QLabel(tr("Width")), self.border_width):
            border_row.addWidget(w)
        border_row.addStretch(1)
        self.background = QCheckBox(tr("Background"))
        self.background.toggled.connect(self.changed)
        self.background_color = ColorButton("#ffffff")
        self.background_color.colorChanged = self.changed
        background_row = QHBoxLayout()
        background_row.addWidget(self.background)
        background_row.addWidget(self.background_color)
        background_row.addStretch(1)
        look = QVBoxLayout()
        look.addLayout(font_row)
        look.addLayout(border_row)
        look.addLayout(background_row)
        look_box = QGroupBox(tr("Appearance"))
        look_box.setLayout(look)

        # ------------------------------------------------- pages
        self.all_pages = QRadioButton(tr("All pages"))
        self.some_pages = QRadioButton(tr("Pages:"))
        self.pages = QLineEdit()
        self.pages.setPlaceholderText(tr("e.g. 9-200 or 1,3,9-"))
        self.pages.setToolTip(tr("The pages of the file, from 1; LAST counts from the end"))
        self.parity = QComboBox()
        for code, title in headfoot.PARITIES.items():
            self.parity.addItem(tr(title), code)
        for w in (self.all_pages, self.some_pages):
            w.toggled.connect(self.changed)
        self.pages.textChanged.connect(lambda *_: (self.some_pages.setChecked(True) if self.pages.text() and
                                                   not self._loading else None, self.changed()))
        self.parity.currentIndexChanged.connect(self.changed)
        pages = QGridLayout()
        pages.addWidget(self.all_pages, 0, 0)
        pages.addWidget(self.some_pages, 1, 0)
        pages.addWidget(self.pages, 1, 1)
        pages.addWidget(QLabel(tr("Of those:")), 2, 0)
        pages.addWidget(self.parity, 2, 1)
        pages_box = QGroupBox(tr("Pages"))
        pages_box.setLayout(pages)

        # ------------------------------------------------- Bates numbering
        self.bates_prefix = QLineEdit()
        self.bates_suffix = QLineEdit()
        self.bates_start = QSpinBox()
        self.bates_start.setRange(0, 999_999_999)
        self.bates_digits = QSpinBox()
        self.bates_digits.setRange(1, 20)
        for w in (self.bates_prefix, self.bates_suffix):
            w.textChanged.connect(self.changed)
        for w in (self.bates_start, self.bates_digits):
            w.valueChanged.connect(self.changed)
        bates = QFormLayout()
        bates.addRow(tr("Prefix"), self.bates_prefix)
        bates.addRow(tr("Starts at"), self.bates_start)
        bates.addRow(tr("Digits"), self.bates_digits)
        bates.addRow(tr("Suffix"), self.bates_suffix)
        bates_box = QGroupBox(tr("Bates numbering ($bates)"))
        bates_box.setLayout(bates)

        # ------------------------------------------------- preview
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW + QSize(8, 8))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background: palette(dark);")
        self.preview_page = QSpinBox()
        self.preview_page.setRange(1, max(self.doc.count, 1))
        self.preview_page.setValue(min(max(page, 1), self.doc.count))
        self.preview_page.setPrefix(tr("Page") + " ")
        self.preview_page.valueChanged.connect(self.changed)
        self.problem = QLabel()
        self.problem.setWordWrap(True)
        self.problem.setStyleSheet("color: #c0392b;")
        self.note = QLabel()
        self.note.setWordWrap(True)
        preview = QVBoxLayout()
        preview.addWidget(self.preview)
        preview.addWidget(self.preview_page)
        preview.addWidget(self.note)
        preview.addWidget(self.problem)
        preview.addStretch(1)
        preview_box = QGroupBox(tr("Preview"))
        preview_box.setLayout(preview)

        # ------------------------------------------------- together
        left = QVBoxLayout()
        left.addWidget(texts_box)
        row = QHBoxLayout()
        row.addWidget(margins_box)
        row.addWidget(look_box, 1)
        left.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(pages_box, 1)
        row.addWidget(bates_box)
        left.addLayout(row)
        body = QHBoxLayout()
        body.addLayout(left, 1)
        body.addWidget(preview_box)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Apply"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(body)
        lay.addWidget(self.buttons)

        self._fill_profiles(hf.name)
        self.profile.currentIndexChanged.connect(self._profile_chosen)
        self.load(hf)

    # ----------------------------------------------------------------- the settings

    def load(self, hf: HeaderFooter):
        """Show the settings of HF."""
        self._loading = True
        for slot, edit in self.slots.items():
            edit.setText(getattr(hf, slot))
        self.units.setCurrentIndex(self.units.findData(hf.units))
        self._units = hf.units
        for side, spin in self.margins.items():
            spin.setValue(getattr(hf, side))
        self.shrink.setChecked(hf.shrink)
        self.font_box.setCurrentIndex(self.font_box.findData(hf.font))
        self.font_size.setValue(hf.size)
        self.color.set_color(hf.color)
        self.bold.setChecked(hf.bold)
        self.italic.setChecked(hf.italic)
        self.border.setChecked(hf.border)
        self.border_color.set_color(hf.border_color)
        self.border_width.setValue(hf.border_width)
        self.background.setChecked(bool(hf.background))
        self.background_color.set_color(hf.background or "#ffffff")
        self.pages.setText(hf.pages)
        (self.some_pages if hf.pages.strip() else self.all_pages).setChecked(True)
        self.parity.setCurrentIndex(self.parity.findData(hf.parity))
        self.bates_prefix.setText(hf.bates_prefix)
        self.bates_start.setValue(hf.bates_start)
        self.bates_digits.setValue(hf.bates_digits)
        self.bates_suffix.setText(hf.bates_suffix)
        self.show_on_menu.setChecked(hf.show_on_menu)
        self._loading = False
        self.changed()

    def value(self) -> HeaderFooter:
        """The settings shown (not checked: see check)."""
        return HeaderFooter(
            **{slot: edit.text() for slot, edit in self.slots.items()},
            units=self.units.currentData(), **{side: spin.value() for side, spin in self.margins.items()},
            shrink=self.shrink.isChecked(), font=self.font_box.currentData(), size=self.font_size.value(),
            color=self.color.color, bold=self.bold.isChecked(), italic=self.italic.isChecked(),
            border=self.border.isChecked(), border_color=self.border_color.color,
            border_width=self.border_width.value(),
            background=self.background_color.color if self.background.isChecked() else "",
            pages=self.pages.text().strip() if self.some_pages.isChecked() else "", parity=self.parity.currentData(),
            bates_prefix=self.bates_prefix.text(), bates_start=self.bates_start.value(),
            bates_digits=self.bates_digits.value(), bates_suffix=self.bates_suffix.text(),
            name=self.profile.currentData() or "", show_on_menu=self.show_on_menu.isChecked())

    def check(self) -> tuple[HeaderFooter | None, list[tuple[int, dict[str, str]]], str]:
        """(the settings, the texts of each page they go on, '') if they are right; else (None, [],
        what is wrong)."""
        try:
            hf = headfoot.check(self.value())
            pages = headfoot.page_texts(hf, self.doc, self.now)
            if not pages:
                raise LabelError(tr("no page is chosen"))
        except LabelError as e:
            return None, [], str(e)
        return hf, pages, ""

    def _units_changed(self, *_):
        """Keep the margins where they are, in the new units."""
        new = self.units.currentData()
        if not self._loading and new != getattr(self, "_units", new):
            factor = headfoot.POINTS[self._units] / headfoot.POINTS[new]
            for spin in self.margins.values():
                spin.setValue(round(spin.value() * factor, 2))
        self._units = new
        self.changed()

    def insert(self, variable: str):
        self.target.insert("$" + variable)
        self.target.setFocus()

    def changed(self, *_):
        if not self._loading:
            self.timer.start()

    # ----------------------------------------------------------------- the preview

    def update_preview(self):
        """Draw the page chosen with these settings, and say what is wrong, if anything."""
        hf, pages, problem = self.check()
        self.problem.setText(problem)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(hf is not None)
        number = self.preview_page.value()
        texts = dict(pages).get(number) if hf is not None else None
        if hf is not None:
            self.note.setText("" if texts is not None else tr("The header and footer don't go on this page."))
        one = pikepdf.new()
        try:
            one.pages.append(self.pdf.pages[number - 1])
            if texts is not None:
                headfoot.stamp_page(one, one.pages[0], hf, texts)
            data = io.BytesIO()
            one.save(data)
        except (pikepdf.PdfError, LabelError, ValueError) as e:
            self.problem.setText(str(e))
            return
        finally:
            one.close()
        self.preview_doc.close()
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(data.getvalue()))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.preview_doc.load(self._buffer)
        size = self.preview_doc.pagePointSize(0).toSize().scaled(PREVIEW, Qt.AspectRatioMode.KeepAspectRatio)
        if size.isEmpty():
            return
        page = QPixmap(size)
        page.fill(QColor("white"))  # (pages are drawn on nothing: on paper here)
        painter = QPainter(page)
        painter.drawImage(0, 0, self.preview_doc.render(0, size))
        painter.end()
        self.preview.setPixmap(page)

    # ----------------------------------------------------------------- profiles

    def _fill_profiles(self, current: str = ""):
        self.profiles = headfoot.read_profiles()
        self.profile.blockSignals(True)
        self.profile.clear()
        self.profile.addItem(tr("(new profile)"), "")
        for name in self.profiles:
            self.profile.addItem(name, name)
        self.profile.setCurrentIndex(max(self.profile.findData(current), 0))
        self.profile.blockSignals(False)
        self.delete.setEnabled(bool(self.profile.currentData()))

    def _profile_chosen(self, *_):
        name = self.profile.currentData()
        self.delete.setEnabled(bool(name))
        if name in self.profiles:
            self.load(self.profiles[name])

    def ask_profile_name(self, current: str) -> str | None:
        name, ok = QInputDialog.getText(self, tr("Save the profile"), tr("The name of the profile:"),
                                        QLineEdit.EchoMode.Normal, current)
        return name.strip() if ok and name.strip() else None

    def save_profile(self) -> bool:
        hf, _, problem = self.check()
        if hf is None:
            QMessageBox.warning(self, tr("Header and Footer"), problem)
            return False
        name = self.ask_profile_name(self.profile.currentData() or "")
        if name is None:
            return False
        try:
            headfoot.save_profile(dataclasses.replace(hf, name=name))
        except (OSError, LabelError) as e:
            QMessageBox.warning(self, tr("Header and Footer"), tr("Could not keep the setting: {error}", error=e))
            return False
        self._fill_profiles(name)
        return True

    def delete_profile(self) -> bool:
        name = self.profile.currentData()
        if not name:
            return False
        try:
            headfoot.delete_profile(name)
        except OSError as e:
            QMessageBox.warning(self, tr("Header and Footer"), tr("Could not keep the setting: {error}", error=e))
            return False
        self._fill_profiles("")
        return True

    def done(self, result: int):
        self.preview_doc.close()
        self.pdf.close()
        super().done(result)


def ask_header_footer(parent: QWidget, hf: HeaderFooter, source: Path, password: str, labels: list[str],
                      page: int = 1) -> HeaderFooter | None:
    """The settings the user applies in the dialog (None if cancelled)."""
    dlg = HeaderFooterDialog(parent, hf, source, password, labels, page)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    hf, _, _ = dlg.check()
    return hf
