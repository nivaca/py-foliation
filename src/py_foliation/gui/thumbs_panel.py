"""The panel of thumbnails: the pages as thumbnails, with their numbers and labels, of a size the
user chooses (the slider, or Ctrl and the mouse wheel); a dock beside the preview that can be
moved, floated or closed."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QListView, QMenu, QSlider, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ..interface import tr
from . import thumbnails
from .arrange_dialog import PageList


class ThumbList(PageList):
    """The pages as thumbnails (dragging them moves them, as in the list of pages); Ctrl and the
    mouse wheel make them bigger or smaller."""

    zoomed = Signal(int)  # (steps: positive, bigger)

    def __init__(self):
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Snap)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_size(self, height: int):
        self.setIconSize(thumbnails.box(height))
        self.setGridSize(thumbnails.grid(height))

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() // 120 or (1 if event.angleDelta().y() > 0 else -1)
            self.zoomed.emit(steps)
            event.accept()
            return
        super().wheelEvent(event)


class ThumbsPanel(QDockWidget):
    """The dock of the thumbnails: a bar of the operations on the pages chosen, the list of them and
    the slider of their size."""

    resized = Signal(int)  # (the new height of the thumbnails)

    def __init__(self, parent, height: int = thumbnails.DEFAULT):
        super().__init__(tr("Thumbnails"), parent)
        self.setObjectName("thumbnails")  # (for the window to keep where it is)
        self.list = ThumbList()
        self.list.setToolTip(tr("Click a page to show it; select pages (Shift, Ctrl) and right-click them for "
                                "more; drag them to move them (with Ctrl, to copy them); Ctrl and the mouse "
                                "wheel change the size"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(thumbnails.SMALLEST, thumbnails.LARGEST)
        self.slider.setSingleStep(8)
        self.slider.setPageStep(32)
        self.slider.setToolTip(tr("The size of the thumbnails (Ctrl and the mouse wheel, too)"))
        self.slider.setValue(height)
        self.slider.valueChanged.connect(self._resized)
        self.list.zoomed.connect(lambda steps: self.slider.setValue(self.slider.value() + 16 * steps))
        row = QHBoxLayout()
        small, big = QLabel("▫"), QLabel("◻")
        row.addWidget(small)
        row.addWidget(self.slider, 1)
        row.addWidget(big)
        self.bar = QToolBar()
        self.bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.bar.setIconSize(QSize(18, 18))
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self.bar)
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        self.setWidget(body)
        self.list.set_size(height)

    def set_actions(self, actions: list[QAction | None], more: QMenu):
        """The bar: ACTIONS (None, a separator) and a button with the menu MORE (all the others)."""
        for action in actions:
            if action is None:
                self.bar.addSeparator()
            else:
                self.bar.addAction(action)
        button = QToolButton()
        button.setText(more.title())
        button.setToolTip(more.title())
        button.setMenu(more)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.bar.addWidget(button)
        self.widget().setMinimumWidth(self.bar.sizeHint().width() + 8)  # (the whole bar, always)

    def height_of_thumbnails(self) -> int:
        return self.slider.value()

    def _resized(self, value: int):
        self.list.set_size(value)
        self.resized.emit(value)
