# py-foliation

*[Leer en español](https://github.com/nivaca/py-foliation/blob/main/README_es.md)*

py-foliation changes the **page labels** of PDF documents: the numbering a PDF
viewer shows for their pages. A book whose front matter is numbered i, ii,
iii … and whose text starts again at 1 can show those numbers in the viewer,
instead of the plain 1, 2, 3 … of the pages of the file. Only the labels
change; the pages themselves are left as they are.

It can also add headers and footers to the pages (the page label, the page
number, the date, Bates numbers or any text), and those do change the pages.
It has a window, for seeing and editing the labels page by page, and a
command line, for doing the same in scripts.

## Installation

There are three ways to install it: the AppImage (nothing to install), the
Fedora package, or from the source.

### AppImage (any Linux)

Download `py-foliation-VERSION-x86_64.AppImage` from the
[releases](https://github.com/nivaca/py-foliation/releases), make it
executable, and run it. It holds its own Python, Qt and everything else, and
runs on Linux with glibc 2.34 or later (Ubuntu 22.04, Debian 12, Fedora 35 and
later).

```bash
chmod +x py-foliation-*-x86_64.AppImage
./py-foliation-*-x86_64.AppImage                   # the window
./py-foliation-*-x86_64.AppImage show book.pdf     # the command line
./py-foliation-*-x86_64.AppImage cli --help        # the list of commands
```

A first argument that is a command (`show`, `set`…), an option, or `cli`
runs the command line; anything else, or nothing, opens the window. Tools
such as AppImageLauncher or Gear Lever add it to the applications menu.

### Fedora (Copr)

```bash
sudo dnf copr enable nivaca/py-foliation
sudo dnf install py-foliation
```

This installs `py-foliation`, `py-foliation-gui`, a menu entry (also offered
for opening PDF files) and the icons, using Fedora's own Python, pikepdf and
PySide6. Updates come with `sudo dnf upgrade`. The packages are built and
signed by [Copr](https://copr.fedorainfracloud.org/coprs/nivaca/py-foliation/).

Each release also has the RPM itself, signed with the author's key, and that
key (`RPM-GPG-KEY-py-foliation`, also in the repository as
[`packaging/RPM-GPG-KEY-py-foliation`](https://github.com/nivaca/py-foliation/blob/main/packaging/RPM-GPG-KEY-py-foliation)).
Its fingerprint is `8187 0643 CA22 1AF9 0C30 554E BE68 32CD 3599 4948`:

```bash
sudo rpm --import RPM-GPG-KEY-py-foliation
sudo dnf install ./py-foliation-*.noarch.rpm
```

### From the source

You need Python 3.15+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nivaca/py-foliation.git    # or https://codeberg.org/nivaca/py-foliation.git
cd py-foliation
uv sync --extra gui      # without --extra gui, only the command line
uv tool install '.[gui]' # optional: makes py-foliation and py-foliation-gui available everywhere
py-foliation-install     # optional: adds the window to the applications menu
```

`py-foliation-install` works on Linux, Windows and macOS, in your own
folders; `--uninstall` removes what it added.

### PDF/A and PDF/X

To save a copy as PDF/A or PDF/X, py-foliation uses another program of
mine, [pdf2iso](https://github.com/nivaca/pdf2iso) (it needs
Ghostscript). py-foliation looks for it, as `pdf2iso` or
`pdf2iso.py`, on the PATH and in `~/bin` and `~/.local/bin` (or, if it is older than its version 2.0, as `py-pdfconform` or `py-pdfconform.py`); a program
started from the menu of the desktop often doesn't have those two folders on
its PATH. If it is elsewhere, give its path in *Settings ▸ pdf2iso…*,
which says which one will be used (it is kept as `pdfconform` in the
configuration file, which the command line reads too). A script that can't
be run by itself is run with `python3`. Without it, those choices are greyed
out and everything else works.

The conversion keeps the page labels and the view when the file is opened.
Ghostscript writes the pages anew, though: in the copy, the headers, footers
and watermarks py-foliation added are part of the pages, and can no longer
be updated or removed. PDF/A and PDF/X can't be protected by a password, so
the copy of a protected file has none.

## The window

    py-foliation-gui [file.pdf]

![The window](https://raw.githubusercontent.com/nivaca/py-foliation/main/docs/img/gui_window_en.png)

Open a PDF (or drop it on the window). The window shows the **ranges** of
labels, each with its first page, its style (1, 2, 3; i, ii, iii; I, II,
III; a, b, c; A, B, C; folios 1r, 1v, 2r; or no number), the number it
starts at, a prefix and a suffix; below them, every page with its label; and
on the right, the chosen page.

![Folios, with thumbnails of the pages](https://raw.githubusercontent.com/nivaca/py-foliation/main/docs/img/gui_folios_en.png)

- **Add a range** starts a new range at the page shown, and so does a
  double-click on a page; **Remove the range** lets the previous range go
  on over its pages; **No labels** removes them all.
- Select pages in the list (with Shift and Ctrl) and right-click them to
  **number them** (in any style, from any start, with a prefix and a
  suffix), **continue the numbering from before** them, **give them one
  label**, **edit their labels one by one**, or leave them with **no
  label**.
- The same menu sets how viewers show the document when they open it (for
  the whole document: PDF has no other way). **Page layout**: Single,
  Single Continuous, Facing (two pages side by side, odd pages on the
  left), Facing Continuous, Cover (like Facing, with the first page alone,
  as the cover of a book) or Cover Continuous; **Page view**: Actual Size,
  Fit to Width or Fit to Page; and **Open the document at page N**. They
  are also in the **View** menu, and are saved with the labels.
- **View ▸ Thumbnails of the pages** shows the pages as thumbnails with
  their labels, to look over a whole book at once.
- **Go to the page labelled…** (Ctrl+L) finds a page by its label: `xii`,
  `12v`, `A-3`.
- **Edit ▸ Undo / Redo** go back and forth over the changes.
- **File ▸ Save** gives the open file the new labels; **Save as ▸ PDF…**
  saves a copy with them, which stays open; **Revert to the labels of the
  file** drops the changes.
- **File ▸ Save as ▸ PDF/A-1b, PDF/A-2b, PDF/A-3b** (for archiving) or
  **PDF/X-4** (for printing) saves a copy with the labels and the rest of the
  changes in that standard, made by pdf2iso (see
  [PDF/A and PDF/X](#pdfa-and-pdfx)). It is an export: the open file stays
  as it was, with its changes still to save.
- **File ▸ Copy the labels of another PDF…** takes them from another file,
  for instance an earlier export of the same book.
- **File ▸ Labels from a list…** reads the label of every page from a text
  file, one on each line, and **Save the labels as a list…** writes one, to
  edit in any editor or spreadsheet.
- **Edit ▸ Copy command line** copies the command that gives the same labels
  to another file.
- **Pages ▸ Header and Footer ▸ Add…** draws a header and a footer on the
  pages, and **Pages ▸ Watermark ▸ Add…** a watermark; the menu of the pages
  does it on the chosen ones (see [Headers and footers](#headers-and-footers)
  and [Watermarks](#watermarks)). They are shown in the preview at once and
  written when the file is saved. A page may have several: the dialog asks
  whether to keep those it has. **Update…** changes the settings of the last
  one added, **Remove all** takes away those py-foliation added, and **Remove
  the Bates numbers** only the headers and footers with Bates numbers.
  Profiles marked **Show on menu** are listed there too, to apply in one
  click.
- **Pages ▸ On several files…** adds or removes headers and footers, Bates
  numbers or watermarks on a list of PDFs at once, in the order of the list
  (the Bates numbers go on from one file to the next), saving them next to
  each file, in another folder, or over the files themselves, with a text
  before or after their names, and as a plain PDF, PDF/A or PDF/X.

Files protected by a password ask for it, and keep their protection when
they are saved.

## The command line

![The command line](https://raw.githubusercontent.com/nivaca/py-foliation/main/docs/img/cli_en.png)

    py-foliation show book.pdf                     # the ranges of labels
    py-foliation show --all book.pdf               # the label of every page
    py-foliation show --label xii book.pdf         # the page labelled xii
    py-foliation set book.pdf 1:r 9:D              # new labels -> book-labelled.pdf
    py-foliation set book.pdf 1:r 9:D -i           # change book.pdf itself
    py-foliation set *.pdf 1:r 9:D -i              # several files at once
    py-foliation set book.pdf 1:r 9:D --dry-run    # only show what it would do
    py-foliation copy old.pdf new.pdf -i           # the labels of old.pdf, to new.pdf
    py-foliation clear book.pdf -o plain.pdf       # no labels
    py-foliation view book.pdf                     # how it opens in a viewer
    py-foliation header-footer book.pdf --footer-center '$pagelabel' -i   # a footer
    py-foliation watermark book.pdf --text DRAFT --opacity 30% -i         # a watermark
    py-foliation set book.pdf 1:r 9:D --conform a-2b   # book-labelled.pdf, as PDF/A-2b

A range is written `PAGES:STYLE[:START[:PREFIX]]`:

| Range           | Pages                     | Labels                       |
|-----------------|---------------------------|------------------------------|
| `1:r`           | from 1 on                 | i, ii, iii …                 |
| `9:D`           | from 9 on                 | 1, 2, 3 …                    |
| `201-214:A`     | 201 to 214                | A … N, then the old numbering goes on |
| `215:D:1:App-`  | from 215 on               | App-1, App-2 …               |
| `5:f:12v`       | from 5 on                 | 12v, 13r, 13v … (folios)     |
| `LAST:-::Cover` | the last page             | Cover                        |

or, with `--range`, as `PAGES [style=S] [start=N] [prefix=P] [suffix=X]`:

    py-foliation set book.pdf --range 1-8 style=roman --range 9- style=arabic
    py-foliation set book.pdf --range 1-4 style=roman 'prefix=[' 'suffix=]' 5:D

`PAGES` is a first page (`9`) or a span (`9-200`, `9..200`, `201-`); `LAST`
and `LAST-N` count from the end. A range without a last page goes on until
the next one; a span is laid over the others, and after it the pages go on
with the numbers they had.

The styles are `D` or `arabic` (1, 2, 3), `r` or `roman` (i, ii, iii), `R` or
`ROMAN` (I, II, III), `a` or `letters` (a, b, c), `A` or `LETTERS` (A, B, C),
`f` or `folio` (1r, 1v, 2r: the recto and verso of each leaf; the start is a
leaf and its side, such as `12v`), and `-` or `none` (the prefix only).

`set` replaces the labels the file had; with `--keep` it changes only the
pages given, and `--remove PAGE` drops the range that starts at PAGE.
`show` prints the command that gives the labels of one file to another.
`--password` opens protected files, which keep their protection.
`--conform` saves the files as PDF/A or PDF/X (`a-1b`, `a-2b`, `a-3b` or
`x-4`), with pdf2iso (see [PDF/A and PDF/X](#pdfa-and-pdfx)); it goes
with every command that writes files.

### Folios, suffixes and any other labels

PDF numbers pages in five styles, with a prefix. Folios, for manuscripts and
early printed books, and labels with something after the number (`[i]`,
`12bis`) are not among them: py-foliation writes those as one label for
each page, and recognises them again when it reads the file, so they are
shown and edited as ranges like any other.

Any numbering at all can be given page by page: `--from-file` (or
**File ▸ Labels from a list…**) reads the label of every page, one on each
line, and finds the fewest ranges that give them:

    py-foliation show --all book.pdf > labels.txt     # edit labels.txt…
    py-foliation set book.pdf --from-file labels.txt -i

### The view when the file is opened

A PDF can say how viewers should show it when they open it (its *initial
view*): the page layout, the page view and the page to start at. It has one
view for the whole document, not one for each page. `view` shows it, and
sets the parts given (the others are kept; `default` leaves a part to the
viewer):

    py-foliation view book.pdf --layout cover --page-view fit-page --open-at 9 -i
    py-foliation view book.pdf --page-view actual-size -i
    py-foliation view book.pdf --open-at default -i

The page layouts are `single` (one page at a time), `single-continuous` (all
the pages in one column), `facing` (two pages at a time, odd pages on the
left), `facing-continuous`, `cover` (like `facing`, with the first page
alone, as the cover of a book) and `cover-continuous`; the page views,
`actual-size`, `fit-width`, `fit-page` or a percentage (`150%`). `show`
prints the view too, when the file has one.

### Headers and footers

A header and a footer have three places each, left, center and right. Their
text can hold variables: `$page` (the page of the file), `$pagelabel`,
`$bookmark` (the bookmark the page is under), `$totalpages`, `$author`,
`$filename`, `$filepath`, `$date` (Nov 28, 2007, or as `--date-format`
says: `long`, `m/d/yy`, `dd/mm/yyyy`, `yyyy-mm-dd` …), `$shortdate`, `$time`,
`$day`, `$month`, `$year`, `$shortyear`, `$hour`, `$longhour`, `$minute`,
`$second`, `$ampm` and `$bates`; `$$` writes a `$`. On the command line, put
such text in single quotes, or the shell reads the variables as its own:

    py-foliation header-footer book.pdf --footer-center 'Page $pagelabel of $totalpages' \
        --header-right '$date' --pages 9- -i
    py-foliation header-footer book.pdf --footer-right '$bates' --bates-prefix ABC- --odd -i
    py-foliation header-footer book.pdf --remove -i

The other options:

- **Margins** (`--units in|cm|pt`, `--top`, `--bottom`, `--left`,
  `--right`): from the edges of the page to the header, the footer and the
  text at the sides. `--shrink` scales the content of the pages down, so
  that the header and footer don't cover it.
- **Appearance**: `--font helvetica|times|courier`, `--size`, `--color`,
  `--bold`, `--italic`, `--border` (with `--border-color` and
  `--border-width`) and `--background`.
- **Pages**: `--pages` (`9-200`, `1,3,9-`; all if not given), and of
  those, `--even` or `--odd`.
- **Bates numbering**: `$bates` writes `--bates-prefix`, a number from
  `--bates-start` with `--bates-digits` digits at least, and
  `--bates-suffix`, counting the pages it goes on.
- **Profiles**: `--save-profile NAME` keeps the settings, `--profile NAME`
  starts from them, and `--list-profiles` and `--delete-profile` manage
  them. The window shares them.

The fonts are the standard fonts of PDF, which every viewer has: they write
Latin script, with its accents and signs, but not Greek or Cyrillic.

A header and footer added to a page replaces those py-foliation added
before, unless `--add` keeps them, so that a page can have several.
`--update` replaces the last one added, starting from its own settings (kept
in the file) with the options given laid over them. `--remove` (or **Remove
all**) puts the pages back exactly as they were, links included, and
`--remove-bates` takes away only the headers and footers with Bates numbers.
`show` lists what py-foliation added to a file.

With several files, the Bates numbers go on from one to the next, in the
order they are given, and the command says which number comes next, to
start the next batch with it:

    py-foliation header-footer vol1.pdf vol2.pdf vol3.pdf --footer-right '$bates' \
        --bates-prefix ABC- --output-dir produced
    Next Bates number: ABC-000913

`--output-dir` saves the files in another folder, with their own names, and
`--name-prefix` and `--name-suffix` add a text before or after the names;
every command that writes files has these options.

### Watermarks

A watermark is a text, such as DRAFT or COPY (it can hold the same
variables), or a page of another PDF, drawn in front of the content of the
pages or behind it:

    py-foliation watermark book.pdf --text DRAFT --opacity 30% --scale 60 -i
    py-foliation watermark book.pdf --text 'Copy for $author' --rotation 0 \
        --vertical bottom --voffset 3 --no-screen -i
    py-foliation watermark book.pdf --file seal.pdf --scale 15 --horizontal right \
        --vertical top --behind -i

- **What**: `--text`, with `--font`, `--size`, `--color`, `--bold` and
  `--italic`; or `--file`, a PDF, and `--file-page`, the page of it to use.
- **Appearance**: `--scale` (the percent of the page it fills; by default
  it keeps its own size), `--rotation` (degrees, counterclockwise; 45 by
  default), `--opacity` (0 to 1, or 0% to 100%), `--behind` (behind the
  content, where a page painted white hides it) and `--no-print` or
  `--no-screen` (shown only on the screen, or only when printing, in the
  viewers that follow such settings).
- **Position**: `--horizontal left|center|right` and `--vertical
  top|center|bottom` (the center by default), moved by `--hoffset` and
  `--voffset` in `--units`.
- **Pages**, **Bates numbering**, **profiles**, `--add`, `--update` and
  `--remove`, as for headers and footers.

### Completion and manual

`py-foliation completion bash|fish|zsh` prints the script that completes
commands, options and files in each shell, for instance:

    py-foliation completion fish > ~/.config/fish/completions/py-foliation.fish

The Fedora package installs them, and the manual page (`man py-foliation`).

## Language

The interface is in English and Spanish. `py-foliation interface es` (or
**Settings ▸ Language** in the window) keeps the choice in
the configuration file; `--interface CODE` changes it for one run.

## Development

    uv sync --all-extras
    uv run pytest

The pictures in this README are made by `uv run python tools/screenshots.py`
(in both languages, without showing anything on the screen), and the icons by
`uv run python tools/icons.py` (with Inkscape) from
`src/py_foliation/icons/py-foliation.svg`.

The AppImage is made by `uv run python tools/bundle-appimage.py`, the signed
RPM by `packaging/build-rpm.sh --sign`, and each release, on GitHub, Codeberg
and Copr, by `uv run python tools/release.py --rpm` (see `packaging/COPR.org`);
`--pypi` also uploads it to PyPI. The manual pages are made from the command
line's help by `uv run python tools/manpage.py` (a test checks they are
up to date).

## License

GNU General Public License, version 3 or later. By
[Nicolas Vaughan](https://nicolasvaughan.org).
