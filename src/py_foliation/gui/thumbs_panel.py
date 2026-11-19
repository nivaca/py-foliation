"""The panel of thumbnails: the pages as thumbnails, with their numbers and labels, of a size the
user chooses (the slider, or Ctrl and the mouse wheel); a dock beside the preview that can be
moved, floated or closed."""

from __future__ import annotations

from PySide6.QtCore import QLine, QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QDrag, QFontMetrics, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QListView, QMenu, QSlider, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ..interface import ntr, tr
from . import thumbnails
from .arrange_dialog import PageList


class ThumbList(PageList):
    """The pages as thumbnails; Ctrl and the mouse wheel make them bigger or smaller.

    Dragging thumbnails moves their pages (with Ctrl, copies them) after the thumbnail under the
    pointer (or the nearest one, in the room between them), which a line under it shows while
    dragging; under the pointer, only how many pages are dragged ("3 pages"). The left half of the first
    thumbnail puts them before it (the line is then above it)."""

    zoomed = Signal(int)  # (steps: positive, bigger)

    def __init__(self):
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        # Static, or Qt moves the thumbnails about by itself (and the pages stay where they were); but
        # Static turns dragging off, so it is turned on again after it.
        self.setMovement(QListView.Movement.Static)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QListView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDropIndicatorShown(False)  # (Qt's frames a thumbnail: a line between them says more)
        self._marker: int | None = None  # (where the pages dragged would go: before this page)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def set_size(self, height: int):
        self.setIconSize(thumbnails.box(height))
        self.setGridSize(thumbnails.grid(height))

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        before = self.before_of(event.position().toPoint()) if event.isAccepted() else None
        if before != self._marker:
            self._marker = before
            self.viewport().update()

    def dragLeaveEvent(self, event):
        self._marker = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._marker = None
        self.viewport().update()
        super().dropEvent(event)

    def before_of(self, pos) -> int:
        """The page (1-based) before which pages dropped at POS go: after the thumbnail at POS, or
        the nearest one; before the first one, on its left half (count + 1: at the end)."""
        if not self.count():
            return 1
        item = self.itemAt(pos) or self._nearest(pos)
        if item is None:
            return self.count() + 1
        row = self.row(item)
        if row == 0 and pos.x() < self.visualItemRect(item).center().x():
            return 1
        return row + 2

    def drag_label(self, count: int) -> QPixmap:
        """What follows the pointer while COUNT pages are dragged: how many they are ("3 pages"),
        in a small box like a tooltip's."""
        text = ntr("{count} page", "{count} pages", count)
        font = self.font()
        metrics = QFontMetrics(font)
        ratio = self.devicePixelRatioF()
        size = QSize(metrics.horizontalAdvance(text) + 12, metrics.height() + 6)
        pixmap = QPixmap(size * ratio)
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        p.setPen(palette.color(QPalette.ColorRole.Mid))
        p.setBrush(palette.color(QPalette.ColorRole.ToolTipBase))
        p.drawRoundedRect(QRectF(0.5, 0.5, size.width() - 1, size.height() - 1), 4, 4)
        p.setFont(font)
        p.setPen(palette.color(QPalette.ColorRole.ToolTipText))
        p.drawText(QRect(QPoint(0, 0), size), Qt.AlignmentFlag.AlignCenter, text)
        p.end()
        return pixmap

    def startDrag(self, actions):
        """A drag of the pages chosen: the pointer, with how many they are below it (no picture of
        them follows it)."""
        items = self.selectedItems()
        if not items:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData(items))
        drag.setPixmap(self.drag_label(len(items)))
        drag.setHotSpot(QPoint(-12, -22))  # (the box below and to the right of the pointer)
        drag.exec(actions, Qt.DropAction.MoveAction)
        self._marker = None
        self.viewport().update()

    def marker_width(self) -> int:
        """The thickness of the line (about a millimetre)."""
        return max(3, round(self.logicalDpiY() / 25.4))

    def marker_line(self) -> QLine | None:
        """The line that shows where the pages dragged would go (None: no drag): under the
        thumbnail they would follow, or above the first one."""
        if self._marker is None or not self.count():
            return None
        grid = self.gridSize()
        if self._marker <= 1:
            rect = self.visualItemRect(self.item(0))
            y = rect.top() + self.marker_width() // 2
        else:
            rect = self.visualItemRect(self.item(min(self._marker, self.count() + 1) - 2))
            y = rect.bottom() + max(grid.height() - rect.height(), self.marker_width()) // 2
        icon = self.iconSize().width()
        left = rect.center().x() - icon // 2
        return QLine(left, y, left + icon, y)

    def paintEvent(self, event):
        super().paintEvent(event)
        line = self.marker_line()
        if line is not None:
            p = QPainter(self.viewport())
            p.setPen(QPen(self.palette().color(QPalette.ColorRole.Highlight), self.marker_width(),
                          Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawLine(line)
            p.end()

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
