"""Thumbnails of the pages of a PDF, of any size (the height of their box, in pixels)."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument

SMALLEST, LARGEST, DEFAULT = 48, 400, 128  # the heights of the thumbnails (pixels)
AT_ONCE = 8  # thumbnails drawn at each turn of the event loop


def box(height: int) -> QSize:
    """The room of a thumbnail of HEIGHT: three quarters of it wide (a portrait page)."""
    return QSize(max(round(height * 0.75), 1), height)


def grid(height: int) -> QSize:
    """The room each page has in the panel, with its number and label below."""
    room = box(height)
    return QSize(max(room.width() + 24, 80), room.height() + 44)


def symbol(text: str, size: int = 32) -> QIcon:
    """An icon drawn from TEXT (one sign), for when the desktop's theme has none."""
    pixmap = _transparent(QSize(size, size), 2.0)
    p = QPainter(pixmap)
    font = p.font()
    font.setPixelSize(round(size * 0.8))
    p.setFont(font)
    p.setPen(QApplication.palette().color(QPalette.ColorRole.WindowText))
    p.drawText(QRect(0, 0, size, size),
               Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return QIcon(pixmap)


def _transparent(size: QSize, ratio: float) -> QPixmap:
    pixmap = QPixmap(size * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QColor(0, 0, 0, 0))
    return pixmap


def blank(height: int = DEFAULT, ratio: float = 1.0) -> QIcon:
    """What a page shows until its thumbnail is drawn (of the full size, so the grid doesn't move)."""
    return QIcon(_transparent(box(height), ratio))


def page_sizes(pdf) -> list[tuple[float, float]]:
    """The sizes (width, height, in points) of the pages of PDF (a pikepdf.Pdf) as they are shown:
    their crop box, turned by their rotation. Read from the file's structure, without drawing
    anything (PDFium would load each page)."""
    sizes = []
    for page in pdf.pages:
        try:
            box_ = [float(v) for v in page.cropbox]
            width, height = abs(box_[2] - box_[0]), abs(box_[3] - box_[1])
            node, angle = page.obj, 0
            while node is not None:  # (/Rotate may be on a parent of the page)
                if "/Rotate" in node:
                    angle = int(node.Rotate)
                    break
                node = node.get("/Parent")
            sizes.append((height, width) if angle % 180 else (width, height))
        except (ValueError, TypeError, AttributeError, IndexError):
            sizes.append((612.0, 792.0))
    return sizes


def frame(image: QImage, height: int, ratio: float = 1.0) -> QIcon:
    """The thumbnail of a page drawn as IMAGE (at RATIO device pixels to a pixel): framed, on white,
    at the bottom of its box of HEIGHT."""
    room = box(height)
    size = (QSize(round(image.width() / ratio), round(image.height() / ratio)) if not image.isNull()
            else room - QSize(2, 2))
    pixmap = _transparent(room, ratio)
    p = QPainter(pixmap)
    x, y = (room.width() - size.width()) // 2, room.height() - size.height() - 1
    p.fillRect(x, y, size.width(), size.height(), QColor("white"))
    if not image.isNull():
        p.drawImage(QRect(x, y, size.width(), size.height()), image)
    p.setPen(QColor(128, 128, 128))
    p.drawRect(x - 1, y - 1, size.width() + 1, size.height() + 1)
    p.end()
    return QIcon(pixmap)


def nbytes(height: int, ratio: float = 1.0) -> int:
    """The memory a thumbnail of HEIGHT takes (about)."""
    room = box(height)
    return int(room.width() * room.height() * 4 * ratio * ratio)


def render(doc: QPdfDocument, page: int, height: int = DEFAULT, ratio: float = 1.0) -> QIcon:
    """The thumbnail of PAGE (1-based) of DOC, drawn here and now (see thumb_renderer for drawing
    them in a thread)."""
    inner = box(height) - QSize(2, 2)
    size = doc.pagePointSize(page - 1).toSize().scaled(inner, Qt.AspectRatioMode.KeepAspectRatio)
    if size.isEmpty():
        size = inner
    image = doc.render(page - 1, size * ratio)
    image.setDevicePixelRatio(ratio)
    return frame(image, height, ratio)
