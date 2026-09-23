"""Tests for markdown-cjk-latin-space-remover.

`FOLDED` and `KEPT` reproduce the boundary and protection cases of the
mdformat plugin's end-to-end suite, with the expected output taken as the
input wherever mdformat merely normalises (`>日本語` stays without the space
mdformat would add). Cases marked `# MIRROR` pair with a case in
typst-cjk-latin-space-remover's suite; keep the two in lockstep. The rest
covers hazards specific to editing source bytes in place.
"""

import subprocess
import sys

import pyromark
import pytest

from markdown_cjk_latin_space_remover import (
    _TRAIL_CJK,
    _deletions,
    _parse,
    _runs,
    format_text,
)
from markdown_cjk_latin_space_remover.__main__ import main

# Inputs whose CJK-adjacent spaces are removed.
FOLDED = [
    pytest.param(
        "これは `code` です\n", "これは`code`です\n", id="code-span"
    ),  # MIRROR: inline raw
    pytest.param(
        "行列 $x$ の計算\n", "行列$x$の計算\n", id="inline-math"
    ),  # MIRROR: inline math
    pytest.param(
        "これは `行 列` です\n", "これは`行 列`です\n", id="code-interior-kept"
    ),  # MIRROR: raw interior kept
    pytest.param(
        "日本語 English テスト\n", "日本語Englishテスト\n", id="run-latin"
    ),  # MIRROR: pure run
    pytest.param(
        "最大 3 個の項目\n", "最大3個の項目\n", id="run-digit"
    ),  # MIRROR: pure run
    pytest.param(
        "日本語 **English** テスト\n", "日本語**English**テスト\n", id="strong"
    ),
    pytest.param("日本語 *English* テスト\n", "日本語*English*テスト\n", id="em"),
    pytest.param("*日本* 語 と\n", "*日本*語と\n", id="after-em"),
    pytest.param(
        "日本語 [English](x) テスト\n", "日本語[English](x)テスト\n", id="link"
    ),
    pytest.param("日本語 ![alt](x) テスト\n", "日本語![alt](x)テスト\n", id="image"),
    pytest.param(
        "日本語 ~~English~~ テスト\n", "日本語~~English~~テスト\n", id="strikethrough"
    ),
    pytest.param("> 日本語 English\n", "> 日本語English\n", id="blockquote"),
    pytest.param("> > 日本語 English\n", "> > 日本語English\n", id="blockquote-nested"),
    pytest.param(
        ">日本語 English\n", ">日本語English\n", id="blockquote-no-space-marker"
    ),
    pytest.param(
        "> 日本語 English\n続き です\n",
        "> 日本語English\n続きです\n",
        id="blockquote-lazy",
    ),
    pytest.param(
        "- [ ] 項目 A\n- [x] 完了 した\n",
        "- [ ] 項目A\n- [x] 完了した\n",
        id="task-list",
    ),
    pytest.param(
        "| 列 | Name |\n| --- | --- |\n| 日本 語 | x |\n",
        "| 列 | Name |\n| --- | --- |\n| 日本語 | x |\n",
        id="table-cell",
    ),
    # Source-byte hazards.
    pytest.param("日本 \\*a 語\n", "日本\\*a語\n", id="run-across-escape"),
    pytest.param("A&amp; 日本\n", "A&amp;日本\n", id="entity-kept-spelled"),
    pytest.param("日本&#32;語 と\n", "日本&#32;語と\n", id="entity-space-not-deleted"),
    pytest.param(
        "日本 English\r\nテスト です\r\n", "日本English\r\nテストです\r\n", id="crlf"
    ),
    pytest.param("日本 English\r", "日本English\r", id="lone-cr"),
    pytest.param("\ufeff日本 English\n", "\ufeff日本English\n", id="bom"),
    pytest.param(
        "[日本 a][z]\n\n[z]: /u\n", "[日本a][z]\n\n[z]: /u\n", id="full-reference-label"
    ),
    pytest.param(
        "[z][] 語\n\n[z]: /u\n", "[z][]語\n\n[z]: /u\n", id="collapsed-reference-fold"
    ),
    pytest.param(
        "詳細は [ドキュメント](https://example.com/) を参照\n",
        "詳細は[ドキュメント](https://example.com/)を参照\n",
        id="link-destination-is-not-a-bare-url",
    ),
    pytest.param("価格は \\$5 です\n", "価格は\\$5です\n", id="escaped-dollar"),
    pytest.param(
        "値 \\\\$x$ です\n", "値\\\\$x$です\n", id="escaped-backslash-then-math"
    ),
    pytest.param(
        "価格は $5 です\n\n日本 English\n",
        "価格は $5 です\n\n日本English\n",
        id="stray-dollar-protects-its-block-only",
    ),
    pytest.param(
        "日本 English\n\n$$\n\n日本 English\n",
        "日本English\n\n$$\n\n日本 English\n",
        id="unpaired-double-dollar-protects-to-end",
    ),
    pytest.param(
        "記法 `$$` と 日本 English\n",
        "記法`$$`と日本English\n",
        id="double-dollar-in-code",
    ),
    pytest.param(
        "```\n$$\n```\n\n日本 English\n",
        "```\n$$\n```\n\n日本English\n",
        id="double-dollar-in-fenced-code",
    ),
    pytest.param(
        '<Diagram :stage="Math.min($clicks, 1)" />\n\n日本 English\n',
        '<Diagram :stage="Math.min($clicks, 1)" />\n\n日本English\n',
        id="dollar-in-html",
    ),
    pytest.param(
        "段落 a\n\n---\n日本語の段落 English です\n---\n",
        "段落a\n\n---\n日本語の段落 English です\n---\n",
        id="mid-document-metadata-kept",
    ),
    pytest.param(
        "日本 **(a)** 語 と English\n",
        "日本 **(a)** 語とEnglish\n",
        id="structure-check-keeps-some",
    ),
]

# Inputs that must come back unchanged.
KEPT = [
    pytest.param("注: これはテスト\n", id="colon"),  # MIRROR: colon kept
    pytest.param("注&#58; これは\n", id="colon-as-entity"),
    pytest.param("注&colon; これは\n", id="colon-as-named-entity"),
    pytest.param("```\nコード ブロック です\n```\n", id="fence"),
    pytest.param("    コード ブロック です\n", id="indented-code"),
    pytest.param("- a\n\n\t\tcode 日本 語\n", id="zero-width-text"),
    pytest.param("式は\n\n$$\nx = 1\n$$\n\nです\n", id="display-math"),
    pytest.param("式は\n\n$$\nx = 1\n$$ (eq)\n\nです\n", id="labelled-display-math"),
    pytest.param("Hello World\n", id="ascii"),
    pytest.param("> Plain English text\n", id="blockquote-latin-only"),
    pytest.param("日本語 _English_ テスト\n", id="underscore-em"),
    pytest.param("日本語 __English__ テスト\n", id="underscore-strong"),
    pytest.param("日本 **(a)** 語\n", id="structure-check-keeps-all"),
    pytest.param("日本 <b>x</b> 語\n", id="inline-html"),
    pytest.param("[日本 a]\n\n[日本 a]: /u\n", id="shortcut-reference-label"),
    pytest.param("[日本 a][]\n\n[日本 a]: /u\n", id="collapsed-reference-label"),
    pytest.param("詳細は https://example.com を参照\n", id="bare-url"),
    pytest.param("詳細は www.example.com を参照\n", id="bare-www"),
    pytest.param("連絡は foo@bar.example.com まで\n", id="bare-email"),
    pytest.param("https://example.com/*日本 語*\n", id="bare-url-into-emphasis"),
    pytest.param("https://example.com/日本 *x*\n", id="bare-url-before-emphasis"),
    pytest.param("前 $ \\text{日本 語} $ 後\n", id="spaced-inline-math"),
    pytest.param("$5\n\n$ \\text{日本 語} $\n", id="currency-then-spaced-math"),
    pytest.param("$$\n日本 語\n=\n日本 語\n$$\n", id="display-math-with-setext-line"),
    pytest.param(
        "$$\n\n日本 語\n\n    $$\n", id="display-math-closed-by-indented-code"
    ),
    pytest.param("$$\n\n日本 語\n\n<!-- $$ -->\n", id="display-math-closed-in-html"),
    pytest.param("", id="empty"),
]

SLIDEV = """\
---
theme: default
title: テンソル ネットワーク
---

# テンソル の縮約

---
layout: center
clicks: 1
---

<ContractionDiagram scene="ttgt" :stage="Math.min($clicks / 3, 1)" />

<div v-click class="term-note">

全次元が $d$ なら $d^5$ が $2d^4$ になる

</div>
"""

SLIDEV_EXPECTED = SLIDEV.replace(
    "全次元が $d$ なら $d^5$ が $2d^4$ になる", "全次元が$d$なら$d^5$が$2d^4$になる"
).replace("# テンソル の縮約", "# テンソルの縮約")

ALL_INPUTS = [p.values[0] for p in FOLDED + KEPT] + [SLIDEV]


@pytest.mark.parametrize(("src", "expected"), FOLDED)
def test_folded(src, expected):
    assert format_text(src) == expected


@pytest.mark.parametrize("src", KEPT)
def test_kept(src):
    assert format_text(src) == src


def test_slidev_deck_keeps_its_front_matter_and_html():
    assert format_text(SLIDEV) == SLIDEV_EXPECTED


@pytest.mark.parametrize(
    ("src", "fragment"),
    [
        ("日本語 **English** テスト\n", "<strong>English</strong>"),
        ("日本語 ~~English~~ テスト\n", "<del>English</del>"),
        ("- [ ] 項目 A\n", 'type="checkbox"'),
        ("| 列 |\n| --- |\n| 日本 語 |\n", "<table>"),
    ],
    ids=["strong", "strikethrough", "task-list", "table"],
)
def test_folded_construct_still_renders(src, fragment):
    options = pyromark.Options.ENABLE_STRIKETHROUGH | pyromark.Options.ENABLE_TASKLISTS
    options |= pyromark.Options.ENABLE_TABLES
    assert fragment in pyromark.html(format_text(src), options=options)


@pytest.mark.parametrize("src", ALL_INPUTS)
def test_only_spaces_are_removed(src):
    out = format_text(src)
    it = iter(src)
    # `out` is a subsequence of `src`, and everything skipped is a space.
    for ch in out:
        for skipped in it:
            if skipped == ch:
                break
            assert skipped == " "
        else:
            pytest.fail(f"{out!r} is not a subsequence of {src!r}")
    assert all(ch == " " for ch in it)


@pytest.mark.parametrize("src", ALL_INPUTS)
def test_idempotent(src):
    once = format_text(src)
    assert format_text(once) == once


def test_trailing_fold_does_not_reach_past_a_newline():
    """`$` would match before the final newline and fold the newline away."""
    assert _TRAIL_CJK.search("日本 \n") is None
    assert _TRAIL_CJK.search("日本 ") is not None


@pytest.mark.parametrize(
    ("src", "folds"),
    [("日本 *a* 語", True), ("日本 _a_ 語", False), ("日本 __a__ 語", False)],
    ids=["asterisk", "underscore", "double-underscore"],
)
def test_emphasis_fold_depends_on_the_marker(src, folds):
    """Decided before the structure check, which would also catch `_`."""
    text = src + "\n"
    events, raw = _parse(text), text.encode()
    positions = set().union(
        *(_deletions(raw, events, run) for run in _runs(raw, events))
    )
    assert bool(positions) is folds


# --- CLI ---------------------------------------------------------------------

CRLF_SRC = "日本 English\r\nテスト です\r\n".encode()
CRLF_OUT = "日本English\r\nテストです\r\n".encode()


def run_cli(*args, stdin=b""):
    return subprocess.run(
        [sys.executable, "-m", "markdown_cjk_latin_space_remover", *args],
        input=stdin,
        capture_output=True,
    )


def test_cli_stdin_is_byte_exact():
    result = run_cli(stdin=CRLF_SRC)
    assert result.returncode == 0
    assert result.stdout == CRLF_OUT


def test_cli_file_to_stdout_is_byte_exact(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(CRLF_SRC)
    result = run_cli(str(path))
    assert result.stdout == CRLF_OUT
    assert path.read_bytes() == CRLF_SRC


def test_cli_in_place_is_byte_exact(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(CRLF_SRC)
    result = run_cli("-i", str(path))
    assert result.returncode == 0
    assert path.read_bytes() == CRLF_OUT


def test_cli_check(tmp_path):
    changed, clean = tmp_path / "changed.md", tmp_path / "clean.md"
    changed.write_bytes(CRLF_SRC)
    clean.write_bytes(CRLF_OUT)
    assert run_cli("--check", str(clean)).returncode == 0
    result = run_cli("--check", str(changed))
    assert result.returncode == 1
    assert changed.read_bytes() == CRLF_SRC
    assert run_cli("--check", stdin=CRLF_SRC).returncode == 1
    assert run_cli("--check", stdin=CRLF_OUT).returncode == 0


def test_cli_diff_keeps_line_endings(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(CRLF_SRC)
    result = run_cli("--diff", str(path))
    assert result.returncode == 0
    assert "-日本 English\r\n".encode() in result.stdout
    assert "+日本English\r\n".encode() in result.stdout
    assert path.read_bytes() == CRLF_SRC


def test_cli_missing_file(tmp_path):
    result = run_cli(str(tmp_path / "missing.md"))
    assert result.returncode == 2
    assert b"not found" in result.stderr


def test_cli_invalid_utf8(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(b"\xff\xfe")
    assert run_cli(str(path)).returncode == 2
    assert run_cli(stdin=b"\xff").returncode == 2


def test_cli_without_files_on_a_terminal(monkeypatch):
    class Terminal:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "argv", ["markdown-cjk-latin-space-remover"])
    monkeypatch.setattr(sys, "stdin", Terminal())
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
