"""The command line: py-foliation show / set / clear / copy / completion / interface."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from datetime import datetime
from pathlib import Path

from . import config, headfoot, interface, labels, view
from .files import open_pdf, read_list, save_pdf
from .interface import N_, ntr, tr
from .labels import LabelError, pages_text, set_command

COMMANDS = ("show", "set", "clear", "copy", "view", "header-footer", "completion", "interface")

SET_EPILOG = N_("""A range is written PAGES:STYLE[:START[:PREFIX]]:

  1:r            pages from 1 on: i, ii, iii ...
  9:D            pages from 9 on: 1, 2, 3 ...
  201-214:A      pages 201 to 214: A ... N (then the old numbering goes on)
  215:D:1:App-   pages from 215 on: App-1, App-2 ...
  5:f:12v        folios from page 5 on: 12v, 13r, 13v ...
  LAST:-::Cover  the last page: Cover

or, with --range, PAGES [style=S] [start=N] [prefix=P] [suffix=X]:

  --range 9-200 style=arabic
  --range 1-4 style=roman prefix=[ suffix=]

PAGES is a first page (9) or a span (9-200, 9..200, 201-); LAST and LAST-N
count from the end. A range without a last page goes on until the next one.

Styles: D or arabic (1, 2, 3), r or roman (i, ii, iii), R or ROMAN (I, II,
III), a or letters (a, b, c), A or LETTERS (A, B, C), f or folio (1r, 1v,
2r: the recto and verso of each leaf; START is a leaf and its side, as
12v), - or none (the prefix only).

Folios and suffixes are not page label styles of PDF: py-foliation writes
them as one label for each page, and recognises them when it reads the
file.

--from-file takes the labels of all the pages, one on each line (as
'show --all' writes them, with or without the page numbers; - is the
standard input), and finds the fewest ranges that give them.""")


VIEW_EPILOG = N_("""Page layouts: single (one page at a time), single-continuous (all the pages
in one column), facing (two pages at a time, odd pages on the left),
facing-continuous (all the pages in two columns), cover (as facing, but the
first page alone, as the cover of a book), cover-continuous.

Page views: actual-size (the size it would be printed), fit-width, fit-page,
or a percentage (150%).

For instance: py-foliation view book.pdf --layout cover --page-view fit-page
--open-at 9 -i""")


HEADER_FOOTER_EPILOG = N_("""The text of each place may hold variables, written with $ (put the text in
single quotes, or the shell takes them as its own): $page, $pagelabel,
$bookmark, $totalpages, $author, $filename, $filepath, $date, $shortdate,
$time, $day, $month, $year, $shortyear, $hour, $longhour, $minute, $second,
$ampm and $bates; $$ writes a $. A new line in the text (\\n in --*-left and
the rest) starts another line.

The fonts are the standard fonts of PDF, which every viewer has: they write
Latin script, with its accents and signs, but not Greek or Cyrillic.

Margins are the distances from the edges of the page to the header, the
footer and the text at the sides. --shrink scales the content of the pages
down so that the header and footer don't cover it.

A header and footer added again to a page replaces the one py-foliation
added before, and --remove takes them away, putting the pages back as they
were. Profiles keep settings to use again (--save-profile NAME, then
--profile NAME); the options given are laid over those of the profile.

For instance: py-foliation header-footer book.pdf --footer-center 'Page
$pagelabel of $totalpages' --header-right '$date' --pages 9- -i""")


def interface_option(argv: list[str]) -> str | None:
    """The value of --interface in ARGV (needed before the parser is built)."""
    for i, tok in enumerate(argv):
        if tok == "--interface" and i + 1 < len(argv):
            return argv[i + 1]
        if tok.startswith("--interface="):
            return tok.split("=", 1)[1]
    return None


def translate_paragraphs(text: str) -> str:
    return "\n\n".join(tr(par) for par in text.split("\n\n"))


def build_parser(prog: str = "py-foliation") -> argparse.ArgumentParser:
    from . import __version__

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--interface", choices=sorted(interface.names()), default=argparse.SUPPRESS,
                        help=tr("the language of the interface, for this run only (to keep a choice, use the "
                                "'interface' command)"))
    parser = argparse.ArgumentParser(
        prog=prog, parents=[common],
        description=tr("Change the page labels of a PDF: the numbering a PDF viewer shows for its pages "
                       "(i, ii, iii ... 1, 2, 3 ... A-1, A-2 ...)."),
        epilog=tr("Run '%(prog)s COMMAND -h' for help on a command. "
                  "'%(prog)s file.pdf' on its own shows the page labels of the file."),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar=tr("COMMAND"))

    def password(sp):
        sp.add_argument("--password", default="", metavar=tr("PASSWORD"),
                        help=tr("the password to open the PDFs (their protection is kept when they are saved)"))

    def output_options(sp, dry_run_help: str | None = None):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("-o", "--output", type=Path,
                       help=tr("output PDF, with one input only (default: <input>-labelled.pdf)"))
        g.add_argument("-i", "--in-place", action="store_true", help=tr("change the input files themselves"))
        sp.add_argument("-n", "--dry-run", action="store_true",
                        help=dry_run_help or tr("show the labels the files would get, without writing anything"))
        password(sp)

    sp = sub.add_parser("show", parents=[common], help=tr("show the page labels of PDFs"),
                        description=tr("Show the ranges of page labels of PDFs, and the command that "
                                       "would give them to another file."))
    sp.add_argument("inputs", nargs="+", type=Path, metavar=tr("FILE"), help=tr("source PDF"))
    g = sp.add_mutually_exclusive_group()
    g.add_argument("-a", "--all", action="store_true", help=tr("show the label of every page"))
    g.add_argument("-l", "--label", metavar=tr("LABEL"),
                   help=tr("show the pages labelled LABEL (if none, those labelled so but for capitals)"))
    password(sp)

    sp = sub.add_parser("set", parents=[common], help=tr("give PDFs new page labels"),
                        description=tr("Give PDFs new page labels, range by range. The labels they had are "
                                       "replaced, unless --keep is given."),
                        epilog=translate_paragraphs(SET_EPILOG), formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("items", nargs="+", metavar=tr("FILE|RANGE"),
                    help=tr("the PDFs (files ending in .pdf), and the ranges: PAGES:STYLE[:START[:PREFIX]]"))
    sp.add_argument("-r", "--range", dest="named", nargs="+", action="append", default=[],
                    metavar=tr("PAGES [KEY=VALUE]"),
                    help=tr("a range: PAGES [style=S] [start=N] [prefix=P] [suffix=X]"))
    sp.add_argument("-f", "--from-file", metavar=tr("LIST"),
                    help=tr("the labels of all the pages, one on each line (- for the standard input)"))
    sp.add_argument("-k", "--keep", action="store_true",
                    help=tr("keep the labels the PDF has, changing only the pages given"))
    sp.add_argument("--remove", type=int, action="append", default=[], metavar=tr("PAGE"),
                    help=tr("drop the range that starts at PAGE (the one before goes on over its pages); "
                            "implies --keep"))
    output_options(sp)

    sp = sub.add_parser("clear", parents=[common], help=tr("remove the page labels of PDFs"),
                        description=tr("Remove the page labels of PDFs: viewers then number their pages "
                                       "1, 2, 3 ..."))
    sp.add_argument("inputs", nargs="+", type=Path, metavar=tr("FILE"), help=tr("source PDF"))
    output_options(sp)

    sp = sub.add_parser("copy", parents=[common], help=tr("give PDFs the page labels of another"),
                        description=tr("Give PDFs the page labels of another PDF, for instance a new export "
                                       "of the same book. If they have fewer pages, the labels of the pages "
                                       "they lack are left out; if they have more, the last range goes on."))
    sp.add_argument("source", type=Path, metavar=tr("FROM"), help=tr("the PDF whose labels are copied"))
    sp.add_argument("inputs", nargs="+", type=Path, metavar=tr("FILE"), help=tr("the PDFs that get them"))
    output_options(sp)

    sp = sub.add_parser("view", parents=[common], help=tr("show or set how PDFs open in a viewer"),
                        description=tr("Show or set the view of PDFs when they are opened: the page "
                                       "layout, the page view and the page they open at. A PDF has one view "
                                       "for the whole document. Without options, the view is shown; the "
                                       "options not given are kept; 'default' leaves that part to the "
                                       "viewer."),
                        epilog=translate_paragraphs(VIEW_EPILOG),
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("inputs", nargs="+", type=Path, metavar=tr("FILE"), help=tr("source PDF"))
    sp.add_argument("--layout", metavar=tr("LAYOUT"), help=tr("the page layout (see below)"))
    sp.add_argument("--page-view", "--zoom", dest="zoom", metavar=tr("VIEW"),
                    help=tr("the page view (see below), or a percentage, as 150%%"))
    sp.add_argument("--open-at", metavar=tr("PAGE"),
                    help=tr("the page it opens at (the pages of the file, from 1; LAST counts from the end)"))
    output_options(sp, tr("show the view the files would get, without writing anything"))

    sp = sub.add_parser("header-footer", parents=[common], help=tr("add headers and footers to PDFs"),
                        description=tr("Draw text at the top and bottom of the pages of PDFs: a header and "
                                       "a footer, each with a left, center and right place, with variables "
                                       "such as the page label or the date. Unlike the labels, they change "
                                       "the pages themselves."),
                        epilog=translate_paragraphs(HEADER_FOOTER_EPILOG),
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("inputs", nargs="*", type=Path, metavar=tr("FILE"), help=tr("source PDF"))
    g = sp.add_argument_group(tr("text"))
    for slot in headfoot.SLOTS:
        g.add_argument("--" + slot.replace("_", "-"), dest=slot, metavar=tr("TEXT"),
                       help=tr("the text of the {place}", place=tr(headfoot.SLOT_TITLES[slot]).lower()))
    g = sp.add_argument_group(tr("margins"))
    g.add_argument("--units", choices=list(headfoot.POINTS), help=tr("the units of the margins (default: cm)"))
    for side in ("top", "bottom", "left", "right"):
        g.add_argument("--" + side, type=float, metavar=tr("SIZE"),
                       help=tr("the {side} margin", side=tr(headfoot.SIDES[side])))
    g.add_argument("--shrink", action=argparse.BooleanOptionalAction, default=None,
                   help=tr("scale the content of the pages down to leave room for the header and footer"))
    g = sp.add_argument_group(tr("appearance"))
    g.add_argument("--font", choices=list(headfoot.FAMILIES), help=tr("the font (default: helvetica)"))
    g.add_argument("--size", type=float, metavar=tr("POINTS"), help=tr("the font size (default: 10)"))
    g.add_argument("--color", metavar="#RRGGBB", help=tr("the color of the text"))
    g.add_argument("--bold", action=argparse.BooleanOptionalAction, default=None, help=tr("bold text"))
    g.add_argument("--italic", action=argparse.BooleanOptionalAction, default=None, help=tr("italic text"))
    g.add_argument("--border", action=argparse.BooleanOptionalAction, default=None,
                   help=tr("a border around each text"))
    g.add_argument("--border-color", metavar="#RRGGBB", help=tr("the color of the border"))
    g.add_argument("--border-width", type=float, metavar=tr("POINTS"), help=tr("the width of the border"))
    g.add_argument("--background", metavar="#RRGGBB", help=tr("a background color behind each text ('none': no background)"))
    g = sp.add_argument_group(tr("pages"))
    g.add_argument("--pages", metavar=tr("PAGES"),
                   help=tr("the pages, as 9-200 or 1,3,9- (default: all; LAST counts from the end)"))
    parity = g.add_mutually_exclusive_group()
    parity.add_argument("--even", dest="parity", action="store_const", const="even", help=tr("even pages only"))
    parity.add_argument("--odd", dest="parity", action="store_const", const="odd", help=tr("odd pages only"))
    parity.add_argument("--all-pages", dest="parity", action="store_const", const="all",
                        help=tr("even and odd pages (with a profile that has only some)"))
    g = sp.add_argument_group(tr("Bates numbering ($bates)"))
    g.add_argument("--bates-prefix", metavar=tr("TEXT"), help=tr("text before the number"))
    g.add_argument("--bates-start", type=int, metavar="N", help=tr("the first number (default: 1)"))
    g.add_argument("--bates-digits", type=int, metavar="N", help=tr("the digits of the number, at least (default: 6)"))
    g.add_argument("--bates-suffix", metavar=tr("TEXT"), help=tr("text after the number"))
    g = sp.add_argument_group(tr("profiles and removing"))
    g.add_argument("--profile", metavar=tr("NAME"), help=tr("start from the settings of this profile"))
    g.add_argument("--save-profile", metavar=tr("NAME"), help=tr("keep these settings as a profile"))
    g.add_argument("--show-on-menu", action=argparse.BooleanOptionalAction, default=None,
                   help=tr("with --save-profile: list the profile in the window's Header and Footer menu"))
    g.add_argument("--list-profiles", action="store_true", help=tr("list the profiles kept"))
    g.add_argument("--delete-profile", metavar=tr("NAME"), help=tr("forget a profile"))
    g.add_argument("--remove", action="store_true",
                   help=tr("take away the headers and footers py-foliation added (on --pages, or all)"))
    output_options(sp, tr("show the header and footer of the first and last pages, without writing anything"))

    sp = sub.add_parser("completion", parents=[common], help=tr("print the completion script of a shell"),
                        description=tr("Print the script that completes py-foliation's commands, options and "
                                       "files in SHELL. For instance: py-foliation completion fish > "
                                       "~/.config/fish/completions/py-foliation.fish"))
    sp.add_argument("shell", choices=["bash", "fish", "zsh"], metavar=tr("SHELL"),
                    help=tr("bash, fish or zsh"))

    sp = sub.add_parser("interface", parents=[common], help=tr("show or choose the language of the interface"),
                        description=tr("The language of the help, the messages and the window. The choice is "
                                       "kept in the configuration file; --interface CODE changes it for one run "
                                       "only."))
    sp.add_argument("language", nargs="?", choices=sorted(interface.names()),
                    help=tr("the language to use from now on; without it, the languages are listed and the "
                            "one in use is marked"))
    return parser


# =========================================================================== commands


def report(error: LabelError) -> None:
    print(tr("error: {error}", error=error), file=sys.stderr)


def show(a) -> int:
    failed = False
    for k, path in enumerate(a.inputs):
        if k and not (a.all or a.label is not None):
            print()
        try:
            with open_pdf(path, password=a.password) as pdf:
                n = len(pdf.pages)
                ranges = labels.read_labels(pdf)
                shown = view.read_view(pdf)
                stamped = headfoot.pages_with(pdf)
        except LabelError as e:
            report(e)
            failed = True
            continue
        prefix = f"{path}: " if len(a.inputs) > 1 else ""
        if a.all:
            for page, label in enumerate(labels.page_labels(ranges, n), 1):
                print(f"{prefix}{page:>6}  {label}")
        elif a.label is not None:
            pages = labels.find_label(ranges, n, a.label)
            if pages:
                print(prefix + ", ".join(map(str, pages)))
            else:
                print(prefix + tr("no page is labelled {label!r}", label=a.label), file=sys.stderr)
                failed = True
        else:
            print_ranges(path, ranges, n, shown)
            if stamped:
                print(ntr("Header and footer added by py-foliation on {count} page: {pages}",
                          "Header and footer added by py-foliation on {count} pages: {pages}", len(stamped),
                          pages=headfoot.compact_pages(stamped)))
    return 1 if failed else 0


def print_ranges(path: Path, ranges: list[labels.Range], n: int, shown: view.View = view.View()) -> None:
    """The ranges of a file (and its view when it is opened, if it has one), and the command that gives
    them to another file."""
    print(ntr("{path}: {count} page", "{path}: {count} pages", n, path=path))
    if not ranges:
        print(tr("No page labels: viewers number the pages 1, 2, 3 ..."))
    else:
        rows = [(pages_text(r, last), labels.describe(r, last), r.spec()) for r, last in labels.spans(ranges, n)]
        w1 = max(len(x[0]) for x in rows)
        w2 = max(len(x[1]) for x in rows)
        for pages, desc, spec in rows:
            print(f"  {pages:<{w1}}  {desc:<{w2}}  {spec}")
    if shown:
        print_view(shown)
    if not ranges:
        return
    print(tr("To give these labels to another file:"))
    print("  " + set_command(Path("FILE.pdf"), ranges).replace("FILE.pdf", tr("FILE.pdf")))


def print_view(v: view.View, title: str | None = None) -> None:
    print(title or tr("When it is opened:"))
    rows = view.describe(v)
    width = max(len(what) for what, _ in rows)
    for what, how in rows:
        print(f"  {what + ':':<{width + 1}}  {how}")


def split_named(groups: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    """The --range groups, and what was given after one of them that is not
    KEY=VALUE (``--range 9-200 style=roman 201:D book.pdf``: argparse gives
    201:D and book.pdf to --range)."""
    named, rest = [], []
    for group in groups:
        named.append([group[0]] + [t for t in group[1:] if "=" in t])
        rest += [t for t in group[1:] if "=" not in t]
    return named, rest


def is_file(item: str) -> bool:
    return item.lower().endswith(".pdf") or (":" not in item and Path(item).is_file())


def output_path(a, path: Path) -> Path:
    if a.in_place:
        return path
    return a.output or path.with_name(path.stem + "-labelled.pdf")


def print_spans(ranges: list[labels.Range], n: int) -> None:
    for r, last in labels.spans(ranges, n):
        print(f"  {pages_text(r, last)}: {labels.describe(r, last)}")


def change(a, inputs: list[Path], make, write=labels.write_labels, describe=print_spans) -> int:
    """Give each of INPUTS what MAKE(pdf, n) returns (with WRITE(pdf, it): page labels
    by default), and save it (or, with --dry-run, only say what it would be);
    then DESCRIBE(it, n)."""
    if a.output is not None and len(inputs) > 1:
        raise LabelError(tr("--output takes one input only; with several, each is saved as "
                            "<input>-labelled.pdf, or changed with --in-place"))
    failed = False
    for path in inputs:
        try:
            with open_pdf(path, a.in_place and not a.dry_run, a.password) as pdf:
                n = len(pdf.pages)
                made = make(pdf, n)
                out = output_path(a, path)
                if a.dry_run:
                    print(ntr("{path} would get ({count} page):", "{path} would get ({count} pages):", n,
                              path=out))
                else:
                    if not a.in_place and out.resolve() == path.resolve():
                        raise LabelError(tr("the output is the input file; use --in-place to change it"))
                    write(pdf, made)
                    save_pdf(pdf, out)
                    print(ntr("Wrote {path} ({count} page)", "Wrote {path} ({count} pages)", n, path=out))
        except LabelError as e:
            report(e)
            failed = True
            continue
        describe(made, n)
    return 1 if failed else 0


def set_labels(a) -> int:
    named, rest = split_named(a.named)
    items = a.items + rest
    inputs = [Path(t) for t in items if is_file(t)]
    compact = [t for t in items if not is_file(t)]
    if not inputs:
        raise LabelError(tr("no PDF given (the files must end in .pdf)"))
    if not (compact or named or a.remove or a.from_file):
        raise LabelError(tr("no ranges given (see py-foliation set -h)"))
    listed = read_list(a.from_file) if a.from_file else None

    def make(pdf, n):
        if listed is not None:
            base = labels.from_list(listed, n)
        else:
            base = labels.read_labels(pdf) if a.keep or a.remove else []
        requests = [labels.parse_compact(s, n) for s in compact] + [labels.parse_named(g, n) for g in named]
        return labels.apply(base, requests, n, a.remove)

    return change(a, inputs, make)


def clear(a) -> int:
    return change(a, a.inputs, lambda pdf, n: [])


def copy(a) -> int:
    with open_pdf(a.source, password=a.password) as pdf:
        source = labels.read_labels(pdf)
    return change(a, a.inputs, lambda pdf, n: [r for r in source if r.page <= n])


def view_command(a) -> int:
    given = {"layout": a.layout, "zoom": a.zoom, "page": a.open_at}
    if all(v is None for v in given.values()):
        if a.output is not None or a.in_place or a.dry_run:
            raise LabelError(tr("nothing to change: give --layout, --page-view or --open-at"))
        failed = False
        for k, path in enumerate(a.inputs):
            try:
                with open_pdf(path, password=a.password) as pdf:
                    shown = view.read_view(pdf)
            except LabelError as e:
                report(e)
                failed = True
                continue
            if k:
                print()
            print_view(shown, f"{path}:")
        return 1 if failed else 0
    return change(a, a.inputs, lambda pdf, n: view.changed(view.read_view(pdf), n, **given),
                  write=view.write_view, describe=lambda v, n: print_view(v, tr("When it is opened:")))


def header_footer_settings(a) -> headfoot.HeaderFooter:
    """The settings the options give, laid over those of --profile (or the defaults)."""
    base = headfoot.HeaderFooter()
    if a.profile:
        profiles = headfoot.read_profiles()
        if a.profile not in profiles:
            raise LabelError(tr("there is no profile {name!r} (see --list-profiles)", name=a.profile))
        base = profiles[a.profile]
    changes = {}
    for slot in headfoot.SLOTS:
        if getattr(a, slot) is not None:
            changes[slot] = getattr(a, slot).replace("\\n", "\n")
    for key in ("units", "top", "bottom", "left", "right", "shrink", "font", "size", "color", "bold", "italic",
                "border", "border_color", "border_width", "pages", "parity", "bates_prefix", "bates_start",
                "bates_digits", "bates_suffix", "show_on_menu"):
        if getattr(a, key) is not None:
            changes[key] = getattr(a, key)
    if a.background is not None:
        changes["background"] = "" if a.background.strip().lower() in ("", "none") else a.background
    if a.save_profile:
        changes["name"] = a.save_profile
    return headfoot.check(dataclasses.replace(base, **changes))


def print_header_footer(made, n: int) -> None:
    change, doc = made
    if change.hf is None:
        print("  " + tr("headers and footers taken away"))
        return
    texts = headfoot.page_texts(change.hf, doc, datetime.now())
    for number, page in (texts[0], texts[-1]) if len(texts) > 1 else texts[:1]:
        print("  " + tr("page {page}", page=number) + ":")
        for slot, text in page.items():
            if text.strip():
                print(f"    {tr(headfoot.SLOT_TITLES[slot])}: {text}".replace("\n", " / "))
    print("  " + ntr("on {count} page", "on {count} pages", len(texts)))


def header_footer(a) -> int:
    if a.list_profiles:
        profiles = headfoot.read_profiles()
        if not profiles:
            print(tr("No profiles kept ({path})", path=headfoot.profiles_path()))
        for name, hf in profiles.items():
            texts = "; ".join(f"{tr(headfoot.SLOT_TITLES[s])}: {t}" for s, t in hf.texts().items() if t.strip())
            print(f"  {'*' if hf.show_on_menu else ' '} {name}  ({texts})")
        return 0
    if a.delete_profile:
        if not headfoot.delete_profile(a.delete_profile):
            raise LabelError(tr("there is no profile {name!r} (see --list-profiles)", name=a.delete_profile))
        print(tr("Profile {name!r} forgotten", name=a.delete_profile))
        return 0
    hf = None if a.remove else header_footer_settings(a)
    if a.save_profile:
        try:
            path = headfoot.save_profile(hf)
        except OSError as e:
            raise LabelError(tr("Could not keep the setting: {error}", error=e)) from None
        print(tr("Profile {name!r} kept in {path}", name=a.save_profile, path=path))
        if not a.inputs:
            return 0
    if not a.inputs:
        raise LabelError(tr("no PDF given (the files must end in .pdf)"))
    pages = a.pages or ""

    def make(pdf, n):
        doc = headfoot.document_of(pdf, Path(pdf.filename))
        change = headfoot.Change(None, pages) if hf is None else headfoot.Change(hf)
        if hf is not None:
            headfoot.page_texts(hf, doc, datetime.now())  # (the texts can be written, before anything is)
        return change, doc

    return change(a, a.inputs, make, write=lambda pdf, made: made[0].apply(pdf, made[1]),
                  describe=print_header_footer)


def completion(a) -> int:
    from .completion import script
    print(script(a.shell, build_parser()), end="")
    return 0


def choose_interface(a) -> int:
    names = interface.names()
    if a.language is None:
        current = interface.code()
        print(tr("Languages of the interface:"))
        for code, name in names.items():
            print(f"  {'*' if code == current else ' '} {code}  {name}")
        print(tr("Configuration file: {path}", path=config.config_path()))
        return 0
    if not interface.use(a.language):
        raise LabelError(tr("the language {code} cannot be used: {error}", code=a.language,
                            error=interface.error()))
    try:
        path = config.set("interface", a.language)
    except OSError as e:
        raise LabelError(tr("Could not keep the setting: {error}", error=e)) from None
    print(tr("The interface is now in {name} (kept in {path}).", name=names[a.language], path=path))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    interface.use_configured(interface_option(argv))
    interface.translate_argparse()
    # "py-foliation file.pdf ..." -> show
    words = [t for i, t in enumerate(argv) if not t.startswith("-") and (i == 0 or argv[i - 1] != "--interface")]
    first = words[0] if words else None
    if first and first not in COMMANDS and first.lower().endswith(".pdf"):
        argv.insert(argv.index(first), "show")
    parser = build_parser()
    a, extra = parser.parse_known_args(argv)
    # (argparse takes the positionals of a command in one go: those after an option are left over)
    if extra and a.command in ("set", "show", "clear", "copy", "view", "header-footer") \
            and not any(t.startswith("-") and t != "-" for t in extra):
        if a.command == "set":
            a.items += extra
        else:
            a.inputs += [Path(t) for t in extra]
    elif extra:
        parser.error(tr("unrecognized arguments: %s") % " ".join(extra))
    if not a.command:
        parser.print_help()
        return 1
    commands = {"show": show, "set": set_labels, "clear": clear, "copy": copy, "view": view_command,
                "header-footer": header_footer,
                "completion": completion, "interface": choose_interface}
    try:
        return commands[a.command](a)
    except LabelError as e:
        report(e)
        return 1
