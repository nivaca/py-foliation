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
- **File ▸ Save** gives the open file the new labels; **Save as…** saves a
  copy with them; **Revert to the labels of the file** drops the changes.
- **File ▸ Copy the labels of another PDF…** takes them from another file,
  for instance an earlier export of the same book.
- **File ▸ Labels from a list…** reads the label of every page from a text
  file, one on each line, and **Save the labels as a list…** writes one, to
  edit in any editor or spreadsheet.
- **Edit ▸ Copy command line** copies the command that gives the same labels
  to another file.
- **Pages ▸ Header and Footer ▸ Add…** draws a header and a footer on the
  pages, and the menu of the pages does it on the chosen ones (see
  [Headers and footers](#headers-and-footers)). They are shown in the
  preview at once and written when the file is saved; **Remove all** takes
  away those py-foliation added. Profiles marked **Show on menu** are listed
  there too, to apply in one click.

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
`$filename`, `$filepath`, `$date` (Nov 28, 2007), `$shortdate`, `$time`,
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
Latin script, with its accents and signs, but not Greek or Cyrillic. A
header and footer added again to a page replaces the one py-foliation added
before, and `--remove` (or **Remove all**) puts the pages back exactly as
they were, links included. `show` says which pages have one.

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
