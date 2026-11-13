How py-foliation was made
=========================

py-foliation changes the page labels of PDF documents: the numbering a
PDF viewer shows for their pages.  A book whose front matter is numbered
i, ii, iii … and whose text starts again at 1, with an appendix A, B, C …
and an unnumbered cover, can show those numbers in the viewer, in its
page box and its table of pages, instead of the plain 1, 2, 3 … of the
pages of the file.  Only the labels change; the pages themselves are left
as they are.  Nicolas Vaughan made it in 2026.  It has a window, for
seeing and editing the labels page by page, and a command line, for doing
the same in scripts, in English or in Spanish.  Here I explain how it was
made, in four stages.

py-foliation is free software, under the GNU General Public License,
version 3 or later.  It is written in Python and stands on pikepdf (based
on QPDF), which reads and writes the PDF files; the window uses PySide6
(Qt 6).  It is a companion to py-imposition, by the same author, and
follows its layout and conventions.

Nicolas Vaughan is Associate Professor of Literature at the School of Arts
and Humanities of the Universidad de los Andes, Bogotá, Colombia.

1. The labels
-------------

A PDF keeps its page labels in a number tree, `/PageLabels`, in its
catalog.  Each entry starts a *range* at a page and gives its style
(arabic numerals, lowercase or uppercase roman numerals, lowercase or
uppercase letters, or no number at all), a prefix, and the number of its
first page; a range lasts until the next one starts.  `labels.py` reads
that tree, however it is built (in one node or in many, with entries
beyond the document, unknown styles or nodes reached twice, all of which
real files have), and writes it back as a single, plain node.

Inside the program the labels are a sorted list of ranges, always with
one at page 1.  Every change is made the same way: the list is turned
into the style, prefix and number of each page, the change is made page
by page, and the pages are put back together into the fewest ranges that
give them.  So a change never has to reason about how ranges overlap, and
two ranges that number the pages in the same way become one.

2. The command line
-------------------

`py-foliation show` lists the ranges of a file, or with `--all` the label
of every page, and prints the command that gives the same labels to
another file.  `set` gives a file new labels; `clear` removes them; and
`interface` chooses the language.  A range is written in one of two ways:
compact, `PAGES:STYLE[:START[:PREFIX]]` (`1:r`, `9:D`, `215:D:1:App-`),
short to type and easy to read back; or named, with `--range PAGES
style=S start=N prefix=P`, wordier but self-explanatory.  Pages may be
counted from the end (`LAST`, `LAST-2`).

A range without a last page goes on until the next one; a span
(`90-95:A`) is laid over the others, and after it the pages go on with
the numbers they would have had, so an appendix can be put in the middle
of a numbering without breaking it.  `set` replaces the labels the file
had, unless `--keep` is given, and `--remove PAGE` drops one range, the
one before going on over its pages.  The result goes to a new file
(`book-labelled.pdf`) unless `--in-place` is given.

3. The window
-------------

The window shows the ranges in a table, each with its first page, its
style, the number it starts at and its prefix, all of which can be
changed in place; below it, every page of the file with its label; and
on the right, the page chosen.  *Add a range* starts one at the page
shown, *Remove the range* lets the one before go on, and *No labels*
removes them all.  Every change can be undone and redone.  The window
also shows the command line that gives the same labels to a file.

*Save* gives the file open its new labels; it writes a new file next to
it and only then puts it in its place, so a failed save never leaves a
broken file.  *Save as…* saves a copy.  While there are changes not
saved, the title bar shows an asterisk, and the window asks before
closing or opening another document.  It remembers its size and the last
ten documents opened.

4. Languages, icon and pictures
-------------------------------

Every text of the program, in the window and on the command line,
including `argparse`'s own messages, goes through `tr()`, and the
translations are in one XML file, `locale/es.xml`, with each text in
English and in Spanish.  The language is chosen in the window
(*Settings*), with `--interface` on the command line, or in
`config.toml` (`py-foliation interface es` keeps it).  The README has a
Spanish version, parallel to the English one.

The icon, a page whose number is on an orange label tag, is drawn as an
SVG, and `tools/icons.py` makes every size of it with Inkscape.
`tools/screenshots.py` takes the pictures of the READMEs, in both
languages, without showing anything on the screen.

Testing
-------

The program has 47 automated tests (`tests/`), run with pytest.  They
check the numbers in every style, the reading of ranges in both forms and
of page numbers, how ranges are laid over each other, and the reading and
writing of the number tree, including odd trees.  The command line is run
from start to end on the example document, docs/example/numbers-100.pdf,
whose pages each show their number, and on broken input.  The window is
tested without a screen, with Qt's offscreen platform: opening, editing,
undoing, saving, saving as, unsaved changes and the language.  Other
tests check that every text has its translation and that none is left
over.  The tests run on every push, on GitHub Actions.
