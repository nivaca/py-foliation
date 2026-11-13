"""The command line: py-foliation show / set / clear / interface."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

import pikepdf
from pikepdf import Pdf

from . import config, interface, labels
from .interface import N_, ntr, tr
from .labels import LabelError

COMMANDS = ("show", "set", "clear", "interface")

SET_EPILOG = N_("""A range is written PAGES:STYLE[:START[:PREFIX]]:

  1:r            pages from 1 on: i, ii, iii ...
  9:D            pages from 9 on: 1, 2, 3 ...
  201-214:A      pages 201 to 214: A ... N (then the old numbering goes on)
  215:D:1:App-   pages from 215 on: App-1, App-2 ...
  LAST:-::Cover  the last page: Cover

or, with --range, PAGES [style=S] [start=N] [prefix=P]:

  --range 9-200 style=arabic
  --range 215- style=arabic start=1 prefix=App-

PAGES is a first page (9) or a span (9-200, 9..200, 201-); LAST and LAST-N
count from the end. A range without a last page goes on until the next one.

Styles: D or arabic (1, 2, 3), r or roman (i, ii, iii), R or ROMAN (I, II,
III), a or letters (a, b, c), A or LETTERS (A, B, C), - or none (the prefix
only).""")


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

    def output_options(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("-o", "--output", type=Path, help=tr("output PDF (default: <input>-labelled.pdf)"))
        g.add_argument("-i", "--in-place", action="store_true", help=tr("change the input file itself"))

    sp = sub.add_parser("show", parents=[common], help=tr("show the page labels of a PDF"),
                        description=tr("Show the ranges of page labels of a PDF, and the command that "
                                       "would give them to another file."))
    sp.add_argument("input", type=Path, help=tr("source PDF"))
    sp.add_argument("-a", "--all", action="store_true", help=tr("show the label of every page"))

    sp = sub.add_parser("set", parents=[common], help=tr("give a PDF new page labels"),
                        description=tr("Give a PDF new page labels, range by range. The labels it had are "
                                       "replaced, unless --keep is given."),
                        epilog=translate_paragraphs(SET_EPILOG), formatter_class=argparse.RawDescriptionHelpFormatter)
    sp.add_argument("input", type=Path, help=tr("source PDF"))
    sp.add_argument("ranges", nargs="*", metavar=tr("RANGE"), help=tr("a range: PAGES:STYLE[:START[:PREFIX]]"))
    sp.add_argument("-r", "--range", dest="named", nargs="+", action="append", default=[],
                    metavar=tr("PAGES [KEY=VALUE]"),
                    help=tr("a range: PAGES [style=S] [start=N] [prefix=P]"))
    sp.add_argument("-k", "--keep", action="store_true",
                    help=tr("keep the labels the PDF has, changing only the pages given"))
    sp.add_argument("--remove", type=int, action="append", default=[], metavar=tr("PAGE"),
                    help=tr("drop the range that starts at PAGE (the one before goes on over its pages); "
                            "implies --keep"))
    output_options(sp)

    sp = sub.add_parser("clear", parents=[common], help=tr("remove the page labels of a PDF"),
                        description=tr("Remove the page labels of a PDF: viewers then number its pages "
                                       "1, 2, 3 ..."))
    sp.add_argument("input", type=Path, help=tr("source PDF"))
    output_options(sp)

    sp = sub.add_parser("interface", parents=[common], help=tr("show or choose the language of the interface"),
                        description=tr("The language of the help, the messages and the window. The choice is "
                                       "kept in the configuration file; --interface CODE changes it for one run "
                                       "only."))
    sp.add_argument("language", nargs="?", choices=sorted(interface.names()),
                    help=tr("the language to use from now on; without it, the languages are listed and the "
                            "one in use is marked"))
    return parser


# =========================================================================== commands


def open_pdf(path: Path, in_place: bool = False) -> Pdf:
    if not path.is_file():
        raise LabelError(tr("{path} not found", path=path))
    try:
        return Pdf.open(path, allow_overwriting_input=in_place)
    except pikepdf.PasswordError:
        raise LabelError(tr("{path} is protected by a password", path=path)) from None
    except pikepdf.PdfError as e:
        raise LabelError(tr("{path} cannot be read as a PDF: {error}", path=path, error=e)) from None


def set_command(input: Path, ranges: list[labels.Range]) -> str:
    """The command line that gives a file these RANGES."""
    if not labels.normalize(ranges):
        return shlex.join(["py-foliation", "clear", str(input)])
    return shlex.join(["py-foliation", "set", str(input)] + [r.spec() for r in labels.normalize(ranges)])


def show(a) -> int:
    with open_pdf(a.input) as pdf:
        n = len(pdf.pages)
        ranges = labels.read_labels(pdf)
    if a.all:
        for page, label in enumerate(labels.page_labels(ranges, n), 1):
            print(f"{page:>6}  {label}")
        return 0
    print(ntr("{path}: {count} page", "{path}: {count} pages", n, path=a.input))
    if not ranges:
        print(tr("No page labels: viewers number the pages 1, 2, 3 ..."))
        return 0
    rows = [(tr("pages {first}-{last}", first=r.page, last=last) if last > r.page
             else tr("page {first}", first=r.page), labels.describe(r, last), r.spec())
            for r, last in labels.spans(ranges, n)]
    w1 = max(len(x[0]) for x in rows)
    w2 = max(len(x[1]) for x in rows)
    for pages, desc, spec in rows:
        print(f"  {pages:<{w1}}  {desc:<{w2}}  {spec}")
    print(tr("To give these labels to another file:"))
    print("  " + set_command(Path("FILE.pdf"), ranges).replace("FILE.pdf", tr("FILE.pdf")))
    return 0


def split_named(groups: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    """The --range groups, and the compact ranges given after one of them
    (``--range 9-200 style=roman 201:D``: argparse gives 201:D to --range)."""
    named, compact = [], []
    for group in groups:
        rest = [t for t in group[1:] if "=" not in t]
        named.append([group[0]] + [t for t in group[1:] if "=" in t])
        compact += rest
    return named, compact


def output_path(a) -> Path:
    if a.in_place:
        return a.input
    return a.output or a.input.with_name(a.input.stem + "-labelled.pdf")


def save(pdf: Pdf, a) -> Path:
    out = output_path(a)
    if not a.in_place and out.resolve() == a.input.resolve():
        raise LabelError(tr("the output is the input file; use --in-place to change it"))
    try:
        pdf.save(out)
    except OSError as e:
        raise LabelError(tr("{path} cannot be written: {error}", path=out, error=e)) from None
    return out


def set_labels(a) -> int:
    named, compact = split_named(a.named)
    if not (a.ranges or compact or named or a.remove):
        raise LabelError(tr("no ranges given (see py-foliation set -h)"))
    with open_pdf(a.input, a.in_place) as pdf:
        n = len(pdf.pages)
        requests = [labels.parse_compact(s, n) for s in a.ranges + compact]
        requests += [labels.parse_named(g, n) for g in named]
        base = labels.read_labels(pdf) if a.keep or a.remove else []
        ranges = labels.apply(base, requests, n, a.remove)
        labels.write_labels(pdf, ranges)
        out = save(pdf, a)
    report(out, ranges, n)
    return 0


def clear(a) -> int:
    with open_pdf(a.input, a.in_place) as pdf:
        n = len(pdf.pages)
        labels.write_labels(pdf, [])
        out = save(pdf, a)
    report(out, [], n)
    return 0


def report(out: Path, ranges: list[labels.Range], n: int) -> None:
    print(ntr("Wrote {path} ({count} page)", "Wrote {path} ({count} pages)", n, path=out))
    for r, last in labels.spans(ranges, n):
        pages = tr("pages {first}-{last}", first=r.page, last=last) if last > r.page \
            else tr("page {first}", first=r.page)
        print(f"  {pages}: {labels.describe(r, last)}")


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
    # "py-foliation file.pdf" -> show
    words = [t for i, t in enumerate(argv) if not t.startswith("-") and (i == 0 or argv[i - 1] != "--interface")]
    first = words[0] if words else None
    if first and first not in COMMANDS and first.lower().endswith(".pdf"):
        argv.insert(argv.index(first), "show")
    parser = build_parser()
    a = parser.parse_args(argv)
    if not a.command:
        parser.print_help()
        return 1
    try:
        return {"show": show, "set": set_labels, "clear": clear, "interface": choose_interface}[a.command](a)
    except LabelError as e:
        print(tr("error: {error}", error=e), file=sys.stderr)
        return 1
