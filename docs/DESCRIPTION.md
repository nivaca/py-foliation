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
made, in nine stages.

py-foliation is free software, under the GNU General Public License,
version 3 or later.  It is written in Python and relies on pikepdf (based
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
had, unless `--keep` is given, and `--remove PAGE` drops one range, and
the one before goes on over its pages.  The result goes to a new file
(`book-labelled.pdf`) unless `--in-place` is given.

3. The window
-------------

The window shows the ranges in a table, each with its first page, its
style, the number it starts at and its prefix, all of which can be
changed in place; below it, every page of the file with its label; and
on the right, the chosen page.  *Add a range* starts one at the page
shown, *Remove the range* lets the one before go on, and *No labels*
removes them all.  Every change can be undone and redone.  The window
also shows the command line that gives the same labels to a file.

*Save* gives the open file its new labels; it writes a new file next to
it and only then puts it in its place, so a failed save never leaves a
broken file.  *Save as…* saves a copy.  While there are unsaved
changes, the title bar shows an asterisk, and the window asks before
closing or opening another document.  It remembers its size and the last
ten documents opened.

4. Languages, icon and pictures
-------------------------------

Every text in the program, in the window and on the command line,
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

5. Packages
-----------

`py-foliation-install` adds the window to the applications menu, with its
icon, in the user's own folders: a .desktop file on Linux, which also
offers py-foliation in the "Open with" menu of PDF files, a shortcut in
the Start menu on Windows, and a small application on macOS.

The AppImage holds a Python of its own, with py-foliation, pikepdf and
PySide6, and runs on almost any Linux; its first argument chooses between
the window and the command line.  Before it is kept, it is run once with
an empty home folder, so it cannot lean on anything installed on the
machine that made it.  For Fedora there is an RPM, made with Fedora's own
Python, pikepdf and PySide6, which runs the whole test suite while it is
built and is signed with the author's key.  `tools/release.py` makes each
release in the same way: it runs the tests, makes the wheel, the source
package, the AppImage and the signed RPM, tags the version, and publishes
it on GitHub, on Codeberg and on Copr.

6. Folios, lists and the rest
-----------------------------

PDF numbers pages in five styles, with a prefix, and nothing else.  The
books py-foliation was made for need more: manuscripts and early printed
books are counted in folios, the recto and verso of each leaf (1r, 1v, 2r
…), and editions mark unnumbered pages in brackets ([i]) or add leaves
(12bis).  So a range may have a sixth style, folios, and a suffix after the
number.  Such a range is *virtual*: it is written in the file as one label
for each page, which any viewer shows as it is, and found again when the
file is read.  To find it, each label is read as a prefix, a number in some
style and a suffix, in every way it can be, and the reading that goes on
from the previous label is chosen; where none does, a page keeps its label
as text.

The same reading turns any list of labels, one for each page, into the
fewest ranges that give them: `--from-file` on the command line, and
*Labels from a list…* in the window, read the list that `show --all` (or
*Save the labels as a list…*) writes, so the labels can be edited in any
editor or spreadsheet and read back.

The rest came from use.  `copy` gives files the labels of another, as when
a book is exported again; `set`, `clear` and `copy` take several files at
once, and `--dry-run` only shows what they would do; `show --label` and
the window's *Go to the page labelled…* find a page by its label.  The
window can show the pages as thumbnails with their labels, and a
double-click on a page starts a range there.  Pages chosen in the list
(with Shift and Ctrl) can be numbered at once, in any style, numbered to
continue from the page before them, given one label, or relabelled one
by one, from the right-click menu.  Protected PDFs are opened with their
password, and keep their protection when they are saved (the first
version took it away).  The command line completes its commands and
options in bash, fish and zsh, and has a manual page, made from its own
help so that the two always agree.  The program can also be published on
PyPI.  (A Flatpak for Flathub was made too, but it was given up before
it was ever submitted.)

7. The view when the file is opened
-----------------------------------

Besides its labels, a PDF can say how viewers should show it when they
open it, its *initial view*: the page layout, the page view and the page to
start at.  It names them as PDF viewers do: the layouts Single,
Single Continuous, Facing (two pages side by side, odd pages on the left),
Facing Continuous, Cover (like Facing, with the first page alone, as the
cover of a book) and Cover Continuous; the page views Actual Size, Fit to
Width and Fit to Page.  These are kept for the whole document, not for
each page or range, in the catalog: `/PageLayout` and `/OpenAction`;
there is no way to give a page a layout of its own that any viewer would
follow.  `view.py` reads and writes them, and changes only the parts that
are asked for, so that what it does not understand, such as an opening
script or the panel beside the pages, is kept unless it is replaced.

`py-foliation view` shows the view of a file, or sets the parts given
(`--layout`, `--page-view`, `--open-at`; `default` leaves a part to the
viewer), and `show` prints it with the labels.  In the window, the menu
on the pages, and the *View* menu, have a *Page layout* and a *Page view*
submenu, and offer to open the document at the chosen page; the view is
undone, redone and saved together with the labels.  (Version 0.5 set the
panel and more zooms too, from a dialog; that proved confusing, and 0.6
keeps to these.)

Version 0.6.1 fixed a hang that had been there from the start.  The
preview shows one page fitted in its frame, and Qt was left to decide
when to show its scroll bars; at some sizes of the window a scroll bar
made the page smaller, so it was no longer needed and went away, which
made the page bigger, so it was needed again, without end, and the window
stopped answering.  A page fitted in its frame needs no scroll bars, so
the preview has none.

To make room for it, the code was rearranged: the numbers in each style
went to `numbers.py`, the reading and writing of files that the command
line and the window share to `files.py`, and the widgets and thumbnails of
the window to modules of their own.

8. Headers and footers
----------------------

Everything before changes what a PDF says about its pages; headers and
footers change the pages.  They have the options PDF editors usually
give them: a left, center and right place in each, with variables (`$pagelabel`,
`$page`, `$totalpages`, `$bookmark`, the date and time, `$bates` …),
margins in inches, centimeters or points, the font, its size, color, bold
and italic, a border and a background, the pages (a list of them, and of
those all, the even or the odd ones), Bates numbering, an option that
shrinks the content of the pages to leave room, and profiles that keep the
settings, some of them listed in the menu.

The text is drawn in the standard fonts of PDF, Helvetica, Times and
Courier, which every viewer has, so nothing has to be embedded and no new
dependency is needed; the price is that they write Latin script only.  To
place text left, centered or right, the program needs the width of every
character: `fontmetrics.py` has them, made by `tools/fontmetrics.py` from
the URW fonts, whose metrics are those of Adobe's.

`headfoot.py` draws them on each page in a content stream of its own,
after the original content, which is wrapped in `q … Q` so that nothing it
leaves set can change them, and marks them as pagination artifacts, as
PDF asks for headers and footers.  On a rotated page they are drawn as the
page is shown, so they stay upright at its top and bottom.  To shrink a
page, its content is scaled and the rectangles of its links are moved with
it.  A record in the page dictionary names everything that was added and
moved, so the header and footer can be taken away again, or replaced by
another, leaving the page exactly as it was.

The command line has `header-footer`, and `show` says which pages have
one.  In the window, a dialog has every option and a preview of any page;
the header and footer are shown at once, in a copy of the file, and are
written when the file is saved, undone and redone like the labels.

9. Several headers and footers, watermarks and batches
------------------------------------------------------

The first headers and footers allowed one on a page: a new one replaced
the old.  But a document may need a running title and, apart from it, a
Bates number that someone else will take away later.  So what py-foliation
adds to a page became a stack of *layers* (`stamps.py`).  Each keeps, in the
page dictionary, its kind, the addition it belongs to (the same on every
page it went on), its settings as JSON, and whether it writes Bates
numbers.  Any layer can then be taken away, not only the last: the
content streams of the others are balanced pairs, and the links each one
moved are put where the layers that are left would have them.  A new
header and footer replaces the ones on its pages unless it is asked to
keep them; *Update* takes the settings of the last one added, from the
file itself, and replaces it; the Bates numbers can be removed and the
rest kept.  Pages marked by version 0.7, with one record and no settings,
are still read and cleaned.

Watermarks (`watermark.py`) are layers of another kind: a text, with the
same variables, or a page of another PDF, made a form XObject, scaled,
turned, placed by its side and an offset, with an opacity set by a
graphics state, in front of the content or behind it.  One shown only
when printing, or only on the screen, goes in an optional content group
whose automatic states say so; the group goes away with the last layer
that uses it.

Bates numbers are meant to run through a whole production of documents,
so they go on from one file to the next: on the command line, through the
files in the order given, and in the window, through a list of files that
*On several files…* lets one put in order.  At the end the program says
which number comes next.  Every command that writes files can now save
them in another folder and add a text before or after their names.  The
date that `$date` writes has a choice of formats, and the dialog inserts
page numbers in the usual forms (1 of n, Page 1 of n …).

Testing
-------

The program has 130 automated tests (`tests/`), run with pytest.  They
check the numbers in every style, the reading of ranges in both forms and
of page numbers, how ranges are laid over each other, the reading and
writing of the number tree, including odd trees, the ranges found in
lists of labels, the view when the file is opened, written and read
back in every form, with what the program does not understand kept, and
headers and footers: their variables, their place on the page, as
pdftotext reads it, on rotated pages too, and their removal, which must
give the pages back byte for byte; several layers on a page, taking one
from between others, updating, the files of 0.7, watermarks of text and
of a page, behind and only for printing, the date formats, and Bates
numbers going on through several files.
The command line is run from start to finish on the example document,
docs/example/numbers-100.pdf, whose pages each show their number, and on
broken input.  The window is tested without a screen, with Qt's
offscreen platform: opening, editing, undoing, saving, saving as,
unsaved changes, the view when the file is opened, the language, and a
preview that settles at every size of the window.  Other tests check
that every text has its translation and that none is left over, the menu
installer on each system, and the packaging files and the signing key.  The tests run on every push, on GitHub Actions.
