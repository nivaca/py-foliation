# py-foliation

*[Leer en español](README_es.md)*

py-foliation changes the **page labels** of PDF documents: the numbering a PDF
viewer shows for their pages. A book whose front matter is numbered i, ii,
iii … and whose text starts again at 1 can show those numbers in the viewer,
instead of the plain 1, 2, 3 … of the pages of the file. Only the labels
change; the pages themselves are left as they are.

It has a window, for seeing and editing the labels page by page, and a
command line, for doing the same in scripts.

## Installation

py-foliation needs Python 3.12 or later. With [uv](https://docs.astral.sh/uv/):

    uv tool install 'py-foliation[gui]'

Without the `[gui]` extra only the command line is installed.

## The window

    py-foliation-gui [file.pdf]

![The window](docs/img/gui_window_en.png)

Open a PDF (or drop it on the window). The window shows the **ranges** of
labels, each with its first page, its style (1, 2, 3; i, ii, iii; I, II,
III; a, b, c; A, B, C; or no number), the number it starts at, and a prefix;
below them, every page with its label; and on the right, the page chosen.

- **Add a range** starts a new range at the page shown;
  **Remove the range** lets the range before go on over its pages;
  **No labels** removes them all.
- **Edit ▸ Undo / Redo** go back and forth over the changes.
- **File ▸ Save** gives the file open the new labels; **Save as…** saves a
  copy with them; **Revert to the labels of the file** drops the changes.
- **Edit ▸ Copy command line** copies the command that gives the same labels
  to another file.

## The command line

![The command line](docs/img/cli_en.png)

    py-foliation show book.pdf                 # the ranges of labels
    py-foliation show --all book.pdf           # the label of every page
    py-foliation set book.pdf 1:r 9:D          # new labels -> book-labelled.pdf
    py-foliation set book.pdf 1:r 9:D -i       # change book.pdf itself
    py-foliation clear book.pdf -o plain.pdf   # no labels

A range is written `PAGES:STYLE[:START[:PREFIX]]`:

| Range           | Pages                     | Labels                       |
|-----------------|---------------------------|------------------------------|
| `1:r`           | from 1 on                 | i, ii, iii …                 |
| `9:D`           | from 9 on                 | 1, 2, 3 …                    |
| `201-214:A`     | 201 to 214                | A … N, then the old numbering goes on |
| `215:D:1:App-`  | from 215 on               | App-1, App-2 …               |
| `LAST:-::Cover` | the last page             | Cover                        |

or, with `--range`, as `PAGES [style=S] [start=N] [prefix=P]`:

    py-foliation set book.pdf --range 1-8 style=roman --range 9- style=arabic

`PAGES` is a first page (`9`) or a span (`9-200`, `9..200`, `201-`); `LAST`
and `LAST-N` count from the end. A range without a last page goes on until
the next one; a span is laid over the others, and after it the pages go on
with the numbers they had.

The styles are `D` or `arabic` (1, 2, 3), `r` or `roman` (i, ii, iii), `R` or
`ROMAN` (I, II, III), `a` or `letters` (a, b, c), `A` or `LETTERS` (A, B, C),
and `-` or `none` (the prefix only).

`set` replaces the labels the file had; with `--keep` it changes only the
pages given, and `--remove PAGE` drops the range that starts at PAGE.
`show` prints the command that gives the labels of one file to another.

## Language

The interface is in English and Spanish. `py-foliation interface es` (or
**Settings ▸ Language of the interface** in the window) keeps the choice in
the configuration file; `--interface CODE` changes it for one run.

## Development

    uv sync --all-extras
    uv run pytest

The pictures of this README are made by `uv run python tools/screenshots.py`
(in both languages, without showing anything on the screen), and the icons by
`uv run python tools/icons.py` (with Inkscape) from
`src/py_foliation/icons/py-foliation.svg`.

## License

GNU General Public License, version 3 or later. By
[Nicolas Vaughan](https://nicolasvaughan.org).
