"""CLI entry point for markdown-cjk-latin-space-remover.

Input and formatted output are bytes, decoded and encoded as UTF-8 with no
newline translation. Status and error messages are printed as text.
"""

import argparse
import sys
from importlib import metadata
from pathlib import Path

from . import format_text


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

    # stdin mode when no files given and stdin is piped
    if not args.files and not sys.stdin.isatty():
        text = _decode("<stdin>", sys.stdin.buffer.read())
        if text is None:
            return 2
        formatted = format_text(text)
        if args.check:
            return 1 if text != formatted else 0
        if args.diff:
            _print_diff("<stdin>", text, formatted)
            return 0
        sys.stdout.buffer.write(formatted.encode())
        return 0

    if not args.files:
        parser.error("no files specified (pipe to stdin or pass file paths)")

    # Every file is read and decoded before any is written.
    contents = []
    for path in args.files:
        if not path.is_file():
            reason = "is not a file" if path.exists() else "not found"
            print(f"error: {path} {reason}", file=sys.stderr)
            return 2
        content = _decode(str(path), path.read_bytes())
        if content is None:
            return 2
        contents.append((path, content))

    any_changed = False
    for path, content in contents:
        formatted = format_text(content)
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
                path.write_bytes(formatted.encode())
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


def _print_diff(name: str, old: str, new: str) -> None:
    import difflib

    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{name}",
        tofile=f"b/{name}",
    )
    sys.stdout.buffer.write("".join(diff).encode())


if __name__ == "__main__":
    sys.exit(main())
