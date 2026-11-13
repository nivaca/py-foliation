"""Completion scripts for bash, fish and zsh, made from the parser of the
command line, so that they always know its commands and options.

    py-foliation completion bash > ~/.local/share/bash-completion/completions/py-foliation
    py-foliation completion fish > ~/.config/fish/completions/py-foliation.fish
    py-foliation completion zsh  > ~/.zfunc/_py-foliation    (with fpath+=~/.zfunc)
"""

from __future__ import annotations

import argparse

PROG = "py-foliation"


def commands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def options(parser: argparse.ArgumentParser) -> list[tuple[list[str], argparse.Action]]:
    return [(a.option_strings, a) for a in parser._actions if a.option_strings]


def _help(action: argparse.Action) -> str:
    text = (action.help or "").split(";")[0].split(" (")[0]
    return text.replace("'", "").replace("\n", " ")[:70]


def bash(parser: argparse.ArgumentParser) -> str:
    cmds = commands(parser)
    cases = []
    for name, sub in cmds.items():
        opts = " ".join(o for strings, _ in options(sub) for o in strings)
        choices = next((" ".join(a.choices) for a in sub._actions if not a.option_strings and a.choices), "")
        cases.append(f'        {name}) opts="{opts}"; words="{choices}" ;;')
    top = " ".join(o for strings, _ in options(parser) for o in strings)
    return f"""# bash completion for {PROG} (made by '{PROG} completion bash')
_py_foliation() {{
    local cur prev cmd opts words i
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    cmd=""
    for ((i = 1; i < COMP_CWORD; i++)); do
        case "${{COMP_WORDS[i]}}" in -*) ;; *) cmd="${{COMP_WORDS[i]}}"; break ;; esac
    done
    case "$prev" in
        --interface) COMPREPLY=($(compgen -W "$({PROG} interface 2>/dev/null | awk 'NR>1 && NF>=2 {{print $(NF-1)}}')" -- "$cur")); return ;;
        -o|--output|-f|--from-file) COMPREPLY=($(compgen -f -- "$cur")); return ;;
        --password|--remove|-l|--label) return ;;
    esac
    if [ -z "$cmd" ]; then
        COMPREPLY=($(compgen -W "{' '.join(cmds)} {top}" -- "$cur"))
        [[ "$cur" != -* ]] && COMPREPLY+=($(compgen -f -X '!*.[pP][dD][fF]' -- "$cur") $(compgen -d -- "$cur"))
        return
    fi
    opts=""; words=""
    case "$cmd" in
{chr(10).join(cases)}
    esac
    if [[ "$cur" == -* ]]; then
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
    elif [ -n "$words" ]; then
        COMPREPLY=($(compgen -W "$words" -- "$cur"))
    else
        COMPREPLY=($(compgen -f -X '!*.[pP][dD][fF]' -- "$cur") $(compgen -d -- "$cur"))
    fi
}}
complete -o filenames -F _py_foliation {PROG}
"""


def fish(parser: argparse.ArgumentParser) -> str:
    cmds = commands(parser)
    lines = [f"# fish completion for {PROG} (made by '{PROG} completion fish')",
             f"complete -c {PROG} -f"]
    for name, sub in cmds.items():
        lines.append(f"complete -c {PROG} -n __fish_use_subcommand -a {name} -d '{_help_of(parser, name)}'")
    for strings, action in options(parser):
        lines.append(_fish_option(strings, action, "__fish_use_subcommand"))
    for name, sub in cmds.items():
        cond = f"'__fish_seen_subcommand_from {name}'"
        for strings, action in options(sub):
            lines.append(_fish_option(strings, action, cond))
        positional = [a for a in sub._actions if not a.option_strings]
        choices = next((a.choices for a in positional if a.choices), None)
        if choices:
            lines.append(f"complete -c {PROG} -n {cond} -a '{' '.join(choices)}'")
        elif positional:
            lines.append(f"complete -c {PROG} -n {cond} -F -a '(__fish_complete_suffix .pdf)'")
    return "\n".join(lines) + "\n"


def _help_of(parser: argparse.ArgumentParser, name: str) -> str:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for choice in action._choices_actions:
                if choice.dest == name:
                    return _help(choice)
    return ""


def _fish_option(strings: list[str], action: argparse.Action, cond: str) -> str:
    parts = [f"complete -c {PROG} -n {cond}"]
    for s in strings:
        parts.append(f"-l {s[2:]}" if s.startswith("--") else f"-s {s[1:]}")
    takes = action.nargs != 0
    if action.choices:
        parts.append(f"-x -a '{' '.join(map(str, action.choices))}'")
    elif takes and any(s in ("-o", "--output", "-f", "--from-file") for s in strings):
        parts.append("-r -F")
    elif takes:
        parts.append("-x")
    parts.append(f"-d '{_help(action)}'")
    return " ".join(parts)


def zsh(parser: argparse.ArgumentParser) -> str:
    return (f"#compdef {PROG}\n# zsh completion for {PROG} (made by '{PROG} completion zsh'): the bash one\n"
            "autoload -U +X bashcompinit && bashcompinit\n" + bash(parser))


def script(shell: str, parser: argparse.ArgumentParser) -> str:
    return {"bash": bash, "fish": fish, "zsh": zsh}[shell](parser)
