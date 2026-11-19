"""The thumbnails drawn away from the window's thread, so that the window never waits for them (a
page of a scanned book can take a tenth of a second or more to draw).

Qt's QPdfPageRenderer draws them in a thread of its own, in C++: a thread of Python would not do,
since PySide keeps Python's lock while PDFium draws, and the window would wait for it all the
same. The renderer has a document of its own for each file it draws from (the preview is written
to a new file after each change), never closed while it draws; the window gives it the pages to
draw, the most wanted first, and changes that list whenever it likes (scrolling, resizing): only a
couple of pages are handed to Qt at a time, so that the list can change."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument, QPdfPageRenderer

from . import thumbnails

AT_ONCE = 2  # pages handed to Qt's thread at a time


class Job:
    """Draw page PAGE (1-based) of the file PATH, HEIGHT pixels high at RATIO, known as KEY; SIZE:
    the page's size (width, height: only their proportion counts), or None to ask PDFium for it
    (which may make the window wait, while PDFium draws)."""

    __slots__ = ("path", "password", "page", "height", "ratio", "key", "size")

    def __init__(self, path: str, password: str, page: int, height: int, ratio: float, key,
                 size: tuple[float, float] | None = None):
        self.path, self.password, self.page = path, password, page
        self.height, self.ratio, self.key, self.size = height, ratio, key, size


class _Source:
    """A file drawn from: its document and Qt's renderer of it."""

    def __init__(self, parent: QObject, path: str, password: str):
        self.path, self.password = path, password
        self.doc = QPdfDocument(parent)
        self.doc.setPassword(password)
        self.doc.load(path)
        self.renderer = QPdfPageRenderer(parent)
        self.renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        self.renderer.setDocument(self.doc)
        self.busy = 0  # (its pages being drawn)

    def close(self):
        self.renderer.deleteLater()
        self.doc.close()
        self.doc.deleteLater()


class ThumbRenderer(QObject):
    """Draws the pages it is given; each one drawn is sent with `drawn` (key, height, image)."""

    drawn = Signal(object, int, QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[Job] = []  # (the next one last)
        self._source: _Source | None = None
        self._old: list[_Source] = []  # (files left, still drawing pages asked for before)
        self._asked: dict[tuple[int, int], tuple[_Source, Job]] = {}  # (source, request) -> job
        self._stopped = False

    def set_jobs(self, jobs: list[Job]):
        """Draw JOBS (in this order) instead of those still waiting."""
        self._jobs = list(reversed(jobs))
        self._pump()

    def pending(self) -> int:
        """The pages still to draw (also those being drawn)."""
        return len(self._jobs) + len(self._asked)

    def stop(self):
        self._stopped = True
        self._jobs = []

    def _source_for(self, job: Job) -> _Source:
        if self._source is None or (self._source.path, self._source.password) != (job.path, job.password):
            if self._source is not None:
                self._old.append(self._source)
            self._source = _Source(self, job.path, job.password)
            self._source.renderer.pageRendered.connect(
                lambda page, size, image, options, request, source=self._source:
                self._rendered(source, request, image))
        return self._source

    def _pump(self):
        while self._jobs and len(self._asked) < AT_ONCE and not self._stopped:
            job = self._jobs.pop()
            source = self._source_for(job)
            if not 0 < job.page <= source.doc.pageCount():
                self.drawn.emit(job.key, job.height, QImage())
                continue
            inner = thumbnails.box(job.height) - QSize(2, 2)
            page_size = (QSizeF(*job.size) if job.size else source.doc.pagePointSize(job.page - 1)).toSize()
            size = page_size.scaled(inner, Qt.AspectRatioMode.KeepAspectRatio)
            if size.isEmpty():
                size = inner
            request = source.renderer.requestPage(job.page - 1, size * job.ratio)
            source.busy += 1
            self._asked[(id(source), request)] = (source, job)
        self._close_old()

    def _rendered(self, source: _Source, request: int, image: QImage):
        found = self._asked.pop((id(source), request), None)
        if found is None:
            return
        source.busy -= 1
        if not self._stopped:
            job = found[1]
            image = QImage(image)  # (a copy of its own)
            image.setDevicePixelRatio(job.ratio)
            self.drawn.emit(job.key, job.height, image)
        self._pump()

    def _close_old(self):
        for source in [s for s in self._old if not s.busy]:
            self._old.remove(source)
            source.close()
