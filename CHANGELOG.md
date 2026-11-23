# Changelog

All notable changes to py-foliation. The releases, with their wheels,
AppImages and RPMs, are on
[Codeberg](https://codeberg.org/nivaca/py-foliation/releases) and
[GitHub](https://github.com/nivaca/py-foliation/releases).

## Unreleased

- **Every release signed**: besides the RPM, each file published (the
  wheel, the source package, the AppImage) comes with its signature
  (`.asc`), with `SHA256SUMS` and its signature, and with the public key;
  the tag of the version is signed too. `tools/release.py` makes the
  signed RPM always (`--no-rpm` leaves it out) and checks each signature
  with the published key before anything is published. The READMEs say
  how to check a download.

## 1.0.2 — 2026-11-21

- `docs/THIRD-PARTY.md` (and `docs/TERCEROS_es.md`, in Spanish) lists the
  open-source software py-foliation uses, to run and to be built, tested
  and packaged, with their licences; the READMEs link to it.

- Python 3.14 or later is needed (it was 3.15): `requires-python`, the
  installers in `installers/` and the READMEs. The tests pass with 3.14;
  the AppImage still carries Python 3.15.
- `installers/install.ps1` stopped on Windows unless Python 3.17 was
  installed: the py launcher writes "No suitable Python runtime found" for
  a version it lacks, and PowerShell took this as an error that ended the
  installer before it tried the next version. The probe is now in a
  try/catch.
- A new job of the workflow installs py-foliation with `installers/` on
  Linux, macOS and Windows, runs the command and uninstalls it. The macOS
  install runs only for release tags, on Mondays and when started by hand,
  as GitHub often has no Mac free.
- `docs/DESCRIPCIÓN_es.md` keeps to six sections, each under 4000
  characters, in the third person.

## 1.0.1 — 2026-11-19

- **Dragging thumbnails.** A drop between thumbnails, or to the right of
  the last one of a row, went to the end of the book; it now goes beside
  the nearest one. The pages go after the thumbnail under the pointer
  (the left half of the first one puts them before it), and a line in the
  accent colour shows where. Only a small note ("3 pages") follows the
  pointer. The move waits until the drag is over, so the question about
  the labels does not open inside it; the same in the list of pages.
- **Installers for Python** on Linux, Windows and macOS:
  `installers/install.py` (standard library only) makes a Python
  environment of its own, installs py-foliation with the window from the
  wheel of the latest release (GitHub, or else Codeberg), links the
  commands in `~/.local/bin` or adds them to the PATH on Windows, and adds
  the menu entry; `--version`, `--from`, `--no-gui`, `--no-menu` and
  `--uninstall`. `install.sh` and `install.ps1` find Python 3.15 or later
  and run it, also as one-line commands.

## 1.0 — 2026-11-19

- **A lighter window.** The thumbnails are drawn by Qt's
  `QPdfPageRenderer` in a thread of its own, those in view first; the page
  sizes come from pikepdf, so the window never waits for PDFium to read
  them.
- Each thumbnail is kept by what it shows (about 256 MB of them), so
  moves, deletions, duplicates, label edits and undo draw none again.
- The choice of pages is copied between the list and the thumbnails at
  once (200 pages: from 2.9 s to 0.08 s), and `arrange.rebuild` changes
  only the pages that change (deleting a page of 1000: from 0.3 s to
  0.04 s).
- The preview is drawn again for a label edit only when a header, footer
  or watermark waiting shows page labels.

## 0.12.1 — 2026-11-18

- Thumbnails can be dragged in their panel again: Qt moved them about by
  itself and took the drags before they could move the pages. A drag
  moves the pages chosen, with Ctrl copies them, and dropped PDFs insert
  their pages.

## 0.12 — 2026-11-18

- A bar at the top of the panel of thumbnails: rotate left and right,
  move one page earlier or later, duplicate, delete, insert a blank page
  or the pages of a PDF, and a More menu with the other operations of the
  Pages menu (the right-click menu has More too). Actions not possible
  are greyed out.
- Keys in the thumbnails and in the list: Ctrl+R, Ctrl+Shift+R,
  Alt+arrows, Ctrl+D and Delete; the pages moved stay chosen.
- View > List of pages hides or shows the list, and this is kept between
  sessions.
- `packaging/build-rpm.sh` copies the newest RPM into `dist/` too, next
  to the wheel, the source package and the AppImage.

## 0.11 — 2026-11-18

- **A panel of thumbnails**: View > Thumbnails (F4) shows the pages in a
  panel beside the preview, which can be moved to another side or float.
  A slider, or Ctrl and the mouse wheel, set their size, from 48 to 400
  pixels. The panel and the list share the current page, the pages
  chosen, the menu, the drags and the dropped PDFs.
- The list of pages stays a list; it no longer turns into thumbnails.

## 0.10 — 2026-11-18

- **Arranging pages**: move, delete, duplicate, reverse, rotate, insert
  blank pages or the pages of another PDF, replace, extract and split
  (`arrange.py`). Duplicated pages keep their annotations, and links to
  deleted pages go to the page after them. Blank pages take the boxes and
  rotation of the page before them.
- The labels follow the pages or stay by position; the page the file
  opens at follows its page.
- `py-foliation pages`: `--order`, `--move`, `--delete`, `--duplicate`,
  `--reverse`, `--rotate`, `--insert-blank`, `--insert`, `--replace`,
  `--extract`, `--split-every`, `--split-at` and `--labels
  follow|position`.
- In the window: drag pages in the list (with Ctrl, copy them), drop PDFs
  to insert their pages, a dialog for each operation in the Pages menu and
  the menu of the pages; undoable, written with Save.

## 0.9 — 2026-11-17

- PDF/A and PDF/X output, made by pdf2iso: File > Save as, `--conform`,
  and Pages > On several files.
- The contact email is now nicolasvaughan@proton.me.

## 0.8 — 2026-11-17

- **Watermarks** (`watermark.py`, `py-foliation watermark`): a text or a
  page of another PDF, turned, scaled, with an opacity, in front of the
  content or behind it, shown only when printing or only on the screen,
  removable and updatable, with profiles.
- **Several headers and footers per page.** What py-foliation adds to a
  page is now a stack of layers (`stamps.py`), and any layer can be taken
  away; the records of 0.7 are still read. `--add` keeps those already on
  the pages, `--update` replaces the last one added, `--remove-bates`
  takes away only those with Bates numbers. `$date` has ten formats
  (`--date-format`).
- **Batches of files**: Bates numbers go on from one file to the next;
  `--output-dir`, `--name-prefix` and `--name-suffix` on every command that
  writes files; Pages > On several files in the window.

## 0.7.1 — 2026-11-17

- Headers and footers work with pikepdf 10.8, Fedora's version, whose
  arrays have no `insert()`.
- The documentation describes the features in their own terms.

## 0.7 — 2026-11-17

- **Headers and footers** (`headfoot.py`, `py-foliation header-footer`):
  left, center and right places; variables (`$page`, `$pagelabel`,
  `$bookmark`, `$totalpages`, `$author`, `$filename`, `$filepath`, the
  date and time, `$bates`); margins in in, cm or pt, and shrinking the
  pages to leave room; the PDF standard fonts, size, color, bold, italic,
  border and background; all, even or odd pages, or a list; Bates
  numbering; profiles in `header-footer.json`.
- They are drawn in a content stream of their own, marked as pagination
  artifacts and upright on rotated pages, and can be removed, which gives
  the page back exactly.
- In the window: Pages > Header and Footer, with a dialog and a preview,
  written with Save, undone and redone.

## 0.6.4 — 2026-11-14

- Python 3.15 or later is needed (it was 3.13); the AppImage carries
  Python 3.15, and Copr no longer builds for Fedora 44.

## 0.6.3 — 2026-11-14

- Python 3.13 or later is needed (it was 3.12).

## 0.6.2 — 2026-11-14

- No Flatpak any more: the manifest, `tools/flatpak-deps.py`,
  `packaging/FLATHUB.org` and their test are removed (it was never
  submitted).
- Plainer English and Spanish in the documentation and the code comments;
  no code changed.

## 0.6.1 — 2026-11-13

- The preview could hang the window at some sizes: a scroll bar made the
  page smaller, which made the scroll bar unneeded, and so on without end.
  The fitted preview now has no scroll bars.

## 0.6 — 2026-11-13

- The view when the file is opened is now a Page layout (Single, Single
  Continuous, Facing, Facing Continuous, Cover, Cover Continuous) and a
  Page view (Actual Size, Fit to Width, Fit to Page), as submenus of the
  menu of the pages and of the View menu. The dialog, the panel and the
  rarer zooms are gone; what is not offered is kept as the file has it.
- `py-foliation view`: `--page-view` (`--zoom` still works) and the new
  layout names; no `--panel`.
- Settings > Language instead of Interface Language.

## 0.5 — 2026-11-13

- **The view when the file is opened**: `view.py` reads and writes
  `/PageLayout`, `/PageMode` and `/OpenAction`, changing only the parts
  asked for. `py-foliation view` shows it or sets `--layout`, `--zoom`,
  `--panel` and `--open-at`; `show` prints it. In the window, File > View
  when opened, and "Open the document at page N".
- Every command takes files after the options, not only `set`.

## 0.4 — 2026-11-13

- The code is split into smaller modules (`numbers.py`, `files.py`,
  `gui/widgets.py`, `gui/thumbnails.py`), shared by the command line and
  the window. Nothing changes for the user.

## 0.3 — 2026-11-12

- In the window, pages chosen in the list (Shift, Ctrl) can be numbered at
  once, numbered on from the page before them, given one label, relabelled
  one by one or left with no label, from a right-click menu; their labels
  can be copied.

## 0.2 — 2026-11-12

- **Folios** (1r, 1v, 2r …) and **suffixes** ([i], 12bis): ranges PDF
  cannot express are written one label per page and recognised again when
  the file is read.
- `set --from-file`, and Labels from a list in the window: the fewest
  ranges that give a list of labels, one per page.
- `copy` gives PDFs the labels of another; `set`, `clear` and `copy` take
  several files, `--dry-run` and `--password`.
- Saving keeps a PDF's encryption: 0.1 removed the protection of the files
  it changed.
- `show --label`; completion for bash, fish and zsh; manual pages in
  English and Spanish.
- In the window: a suffix column, thumbnails of the pages, going to a page
  by its label, and a password prompt.
- Metadata for PyPI and `release.py --pypi`; the RPM installs the manual
  pages, completions and AppStream metainfo.

## 0.1 — 2026-11-12

- First version: py-foliation changes the page labels of PDF documents,
  the numbering a viewer shows for their pages. It reads and writes the
  `/PageLabels` tree and gives the fewest ranges.
- Command line: `show` (with `--all`), `set` (ranges as
  `PAGES:STYLE[:START[:PREFIX]]` or `--range`, `--keep`, `--remove`,
  `--in-place`), `clear` and `interface`.
- A window (`py-foliation-gui`): a table of ranges edited in place, every
  page with its label, a preview, undo and redo, recent files.
- English and Spanish interface.
- `py-foliation-install` adds the window to the applications menu; an
  AppImage, a signed RPM and Copr builds; `tools/release.py` publishes a
  release on GitHub, Codeberg and Copr.
