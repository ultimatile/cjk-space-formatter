"""CLI entry point for markdown-cjk-latin-space-remover.

Input and formatted output are bytes, decoded and encoded as UTF-8 with no
newline translation. Status and error messages are printed as text.
"""

import argparse
import sys
from importlib import metadata
from pathlib import Path

from . import _format_text


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="markdown-cjk-latin-space-remover",
        description="Remove spaces next to CJK characters in Markdown files",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {metadata.version('markdown-cjk-latin-space-remover')}",
    )
    parser.add_argument("files", nargs="*", type=Path, help="files to format")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit with 1 if any file would be changed",
    )
    parser.add_argument(
        "-i", "--in-place", action="store_true", help="modify files in place"
    )
    parser.add_argument(
        "--diff", action="store_true", help="show unified diff of changes"
    )

    args = parser.parse_args()

    # stdin mode when no files are given and stdin is not a terminal
    if not args.files and not sys.stdin.isatty():
        text = _decode("<stdin>", sys.stdin.buffer.read())
        if text is None:
            return 2
        formatted = _format("<stdin>", text)
        if formatted is None:
            return 2
        if args.check:
            return 1 if text != formatted else 0
        if args.diff:
            _print_diff("<stdin>", text, formatted)
            return 0
        sys.stdout.buffer.write(formatted.encode())
        return 0

    if not args.files:
        parser.error("no files specified (pipe to stdin or pass file paths)")

    # Every file is read, decoded, and formatted before any is written.
    results = []
    for path in args.files:
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return 2
        if path.is_dir():
            print(f"error: {path} is a directory", file=sys.stderr)
            return 2
        try:
            data = path.read_bytes()
        except OSError as exc:
            print(f"error: {path}: {exc.strerror}", file=sys.stderr)
            return 2
        content = _decode(str(path), data)
        if content is None:
            return 2
        formatted = _format(str(path), content)
        if formatted is None:
            return 2
        results.append((path, content, formatted))

    any_changed = False
    for path, content, formatted in results:
        changed = content != formatted

        any_changed |= changed
        if args.check:
            if changed:
                print(f"would reformat {path}")
        elif args.diff:
            if changed:
                _print_diff(str(path), content, formatted)
        elif args.in_place:
            if changed:
                try:
                    path.write_bytes(formatted.encode())
                except OSError as exc:
                    print(f"error: {path}: {exc.strerror}", file=sys.stderr)
                    return 2
                print(f"reformatted {path}")
        else:  # a filter: the output is the whole file, changed or not
            sys.stdout.buffer.write(formatted.encode())

    return 1 if args.check and any_changed else 0


def _decode(name: str, data: bytes) -> str | None:
    try:
        return data.decode()
    except UnicodeDecodeError as exc:
        print(f"error: {name} is not valid UTF-8: {exc}", file=sys.stderr)
        return None


def _format(name: str, text: str) -> str | None:
    try:
        formatted, dollar_line = _format_text(text)
    except RuntimeError as exc:
        print(f"error: {name}: {exc}", file=sys.stderr)
        return None
    if dollar_line is not None:
        print(
            f"warning: {name}: left unchanged: unescaped '$' on line {dollar_line}",
            file=sys.stderr,
        )
    return formatted


def _print_diff(name: str, old: str, new: str) -> None:
    import difflib

    diff = difflib.unified_diff(
        _lines(old),
        _lines(new),
        fromfile=f"a/{name}",
        tofile=f"b/{name}",
    )
    for line in diff:
        if not line.endswith("\n"):
            line += "\n\\ No newline at end of file\n"
        sys.stdout.buffer.write(line.encode())


def _lines(text: str) -> list[str]:
    """Split at `\\n` only, keeping it; the last line may lack one."""
    lines = text.split("\n")
    return [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])


if __name__ == "__main__":
    sys.exit(main())
