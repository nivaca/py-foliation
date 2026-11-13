"""Thumbnails of the pages of a PDF."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument

THUMB = QSize(96, 128)  # the largest thumbnail of a page
GRID = QSize(THUMB.width() + 28, THUMB.height() + 48)  # the room each page has, with its label
AT_ONCE = 8  # thumbnails drawn at each turn of the event loop


def _transparent() -> QPixmap:
    pixmap = QPixmap(THUMB)
    pixmap.fill(QColor(0, 0, 0, 0))
    return pixmap


def blank() -> QIcon:
    """What a page shows until its thumbnail is drawn (of the full size, so the grid doesn't move)."""
    return QIcon(_transparent())


def render(doc: QPdfDocument, page: int) -> QIcon:
    """The thumbnail of PAGE (1-based), framed, centred in a THUMB-sized picture."""
    room = THUMB - QSize(2, 2)
    size = doc.pagePointSize(page - 1).toSize().scaled(room, Qt.AspectRatioMode.KeepAspectRatio)
    if size.isEmpty():
        size = room
    image = doc.render(page - 1, size)
    pixmap = _transparent()
    p = QPainter(pixmap)
    x, y = (THUMB.width() - size.width()) // 2, THUMB.height() - size.height() - 1
    p.fillRect(x, y, size.width(), size.height(), QColor("white"))
    p.drawImage(x, y, image)
    p.setPen(QColor(128, 128, 128))
    p.drawRect(x - 1, y - 1, size.width() + 1, size.height() + 1)
    p.end()
    return QIcon(pixmap)
