"""CLI entry point for cjk-space-formatter."""

import argparse
import sys
from pathlib import Path

from . import format_text


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="cjk-space-formatter",
        description="Remove unnecessary spaces between CJK and non-CJK characters",
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
        text = sys.stdin.read()
        formatted = format_text(text)
        if args.check:
            return 1 if text != formatted else 0
        if args.diff:
            _print_diff("<stdin>", text, formatted)
            return 0
        sys.stdout.write(formatted)
        return 0

    if not args.files:
        parser.error("no files specified (pipe to stdin or pass file paths)")

    any_changed = False
    for path in args.files:
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return 2

        content = path.read_text(encoding="utf-8")
        formatted = format_text(content)
        changed = content != formatted

        if changed:
            any_changed = True
            if args.check:
                print(f"would reformat {path}")
            elif args.diff:
                _print_diff(str(path), content, formatted)
            elif args.in_place:
                path.write_text(formatted, encoding="utf-8")
                print(f"reformatted {path}")
            else:
                sys.stdout.write(formatted)

    return 1 if args.check and any_changed else 0


def _print_diff(name: str, old: str, new: str) -> None:
    import difflib

    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{name}",
        tofile=f"b/{name}",
    )
    sys.stdout.writelines(diff)


if __name__ == "__main__":
    sys.exit(main())
