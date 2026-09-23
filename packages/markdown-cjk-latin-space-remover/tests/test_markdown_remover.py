"""Tests for markdown-cjk-latin-space-remover.

`FOLDED` holds inputs with their expected output after spaces are removed;
`KEPT` holds inputs that must come back unchanged. Cases marked `# MIRROR`
carry the same label in typst-cjk-latin-space-remover's suite and in
mdformat-no-cjk-latin-space's; keep the three in lockstep.
"""

import io
import os
import subprocess
import sys

import pyromark
import pytest

import markdown_cjk_latin_space_remover
import markdown_cjk_latin_space_remover.__main__
from markdown_cjk_latin_space_remover import (
    _TRAIL_CJK,
    _deletions,
    _Event,
    _parse,
    _pass,
    _Run,
    _runs,
    format_text,
)
from markdown_cjk_latin_space_remover.__main__ import main

# Inputs whose CJK-adjacent spaces are removed.
FOLDED = [
    pytest.param(
        "これは `code` です\n", "これは`code`です\n", id="code-span"
    ),  # MIRROR: inline raw boundary
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
        "![z][] 語\n\n[z]: /i.png\n",
        "![z][]語\n\n[z]: /i.png\n",
        id="collapsed-image-reference-fold",
    ),
    pytest.param(
        "詳細は [ドキュメント](https://example.com/) を参照\n",
        "詳細は[ドキュメント](https://example.com/)を参照\n",
        id="link-destination-is-not-a-bare-url",
    ),
    pytest.param("価格は \\$5 です\n", "価格は\\$5です\n", id="escaped-dollar"),
    pytest.param("価格は &#36;5 です\n", "価格は&#36;5です\n", id="dollar-as-entity"),
    pytest.param(
        "値 \\\\$x$ です\n", "値\\\\$x$です\n", id="escaped-backslash-then-math"
    ),
    pytest.param(
        "記法 `$$` と 日本 English\n",
        "記法`$$`と日本English\n",
        id="double-dollar-in-code",
    ),
    pytest.param(
        '+++\ntitle = "日本 語"\n+++\n\n日本 English\n',
        '+++\ntitle = "日本 語"\n+++\n\n日本English\n',
        id="toml-front-matter",
    ),
    pytest.param(
        "---\na: $$\n---\n\n日本 English\n",
        "---\na: $$\n---\n\n日本English\n",
        id="double-dollar-in-front-matter",
    ),
    pytest.param("日本 $$x$$ 語\n", "日本$$x$$語\n", id="inline-display-math"),
    pytest.param(
        "[https://example.com を参照](x)\n",
        "[https://example.comを参照](x)\n",
        id="url-in-link-text-is-not-bare",
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
        "段落 a\n\n+++\n日本語の段落 English です\n+++\n",
        "段落a\n\n+++\n日本語の段落 English です\n+++\n",
        id="mid-document-toml-metadata-kept",
    ),
    pytest.param(
        "段落 a\n\n---\n日本語の段落 English です\n...\n",
        "段落a\n\n---\n日本語の段落 English です\n...\n",
        id="metadata-closed-by-dots",
    ),
    pytest.param(
        "---\nt: $x\n---\n\n日本 English\n",
        "---\nt: $x\n---\n\n日本English\n",
        id="dollar-in-front-matter",
    ),
    pytest.param(
        "日本 **(a)** 語 と English\n",
        "日本 **(a)** 語とEnglish\n",
        id="structure-check-keeps-some",
    ),
    pytest.param(
        "式 $\\text{日本 語}$ と\n", "式$\\text{日本 語}$と\n", id="math-interior-kept"
    ),
    pytest.param(
        "記号 * 日本語* と *強調*です\n",
        "記号* 日本語*と *強調*です\n",
        id="structure-check-keeps-emphasis-content",
    ),
    pytest.param(
        "日本 [a](x$$y) 語\n\n日本 English\n",
        "日本[a](x$$y)語\n\n日本English\n",
        id="double-dollar-in-link-destination",
    ),
    pytest.param(
        '<div title="$$"></div>\n\n日本 English\n',
        '<div title="$$"></div>\n\n日本English\n',
        id="double-dollar-in-html",
    ),
    pytest.param(
        "    $$\n\n日本 English\n",
        "    $$\n\n日本English\n",
        id="double-dollar-in-indented-code",
    ),
    pytest.param(
        "﻿---\ntitle: 日本 語\n---\n\n日本 English\n",
        "﻿---\ntitle: 日本 語\n---\n\n日本English\n",
        id="front-matter-after-bom",
    ),
]

# Inputs that must come back unchanged.
KEPT = [
    pytest.param("注: これはテスト\n", id="colon"),  # MIRROR: colon kept
    pytest.param("注&#58; これは\n", id="colon-as-entity"),
    pytest.param("注&colon; これは\n", id="colon-as-named-entity"),
    pytest.param("```\nコード ブロック です\n```\n", id="fence"),
    pytest.param("    コード ブロック です\n", id="indented-code"),
    pytest.param("- a\n\n\t\tcode 日本 語\n", id="indented-code-in-list"),
    pytest.param("式は\n\n$$\nx = 1\n$$\n\nです\n", id="display-math"),
    pytest.param("式は\n\n$$\nx = 1\n$$ (eq)\n\nです\n", id="labelled-display-math"),
    pytest.param("Hello World\n", id="ascii"),
    pytest.param("> Plain English text\n", id="blockquote-latin-only"),
    pytest.param("日本語 _English_ テスト\n", id="underscore-em"),
    pytest.param("日本語 __English__ テスト\n", id="underscore-strong"),
    pytest.param("日本 **(a)** 語\n", id="structure-check-keeps-all"),
    pytest.param("日本 <b>x</b> 語\n", id="inline-html"),
    pytest.param("<div>\n日本 語\n</div>\n", id="html-block"),
    pytest.param("日本 <https://a.com/$x> 語\n", id="dollar-in-autolink-text"),
    pytest.param("[日本 a]\n\n[日本 a]: /u\n", id="shortcut-reference-label"),
    pytest.param("[日本 a][]\n\n[日本 a]: /u\n", id="collapsed-reference-label"),
    pytest.param(
        "![日本 a][]\n\n[日本 a]: /i.png\n", id="collapsed-image-reference-label"
    ),
    pytest.param(
        "![日本 a]\n\n[日本 a]: /i.png\n", id="shortcut-image-reference-label"
    ),
    pytest.param("詳細は https://example.com を参照\n", id="bare-url"),
    pytest.param("詳細は www.example.com を参照\n", id="bare-www"),
    pytest.param("詳細は HTTPS://EXAMPLE.COM を参照\n", id="bare-url-uppercase"),
    pytest.param("詳細は WWW.EXAMPLE.COM を参照\n", id="bare-www-uppercase"),
    pytest.param("連絡は foo@bar.example.com まで\n", id="bare-email"),
    pytest.param("連絡は mailto:foo@bar.example.com まで\n", id="bare-mailto"),
    pytest.param("連絡は xmpp:foo@bar.example.com まで\n", id="bare-xmpp"),
    pytest.param("https://example.com/*日本 語*\n", id="bare-url-into-emphasis"),
    pytest.param("https://example.com/日本 *x*\n", id="bare-url-before-emphasis"),
    pytest.param("詳細は https://ex.com/$x$ を参照\n", id="bare-url-containing-math"),
    pytest.param("[x](https://a.com/)https://b.com 日本\n", id="bare-url-after-link"),
    pytest.param("`https://a.com/`https://b.com 日本\n", id="bare-url-after-code-span"),
    pytest.param("<https://a.com/>https://b.com 日本\n", id="bare-url-after-autolink"),
    pytest.param("前 $ \\text{日本 語} $ 後\n", id="spaced-inline-math"),
    pytest.param("価格 \\\\$5 です\n", id="escaped-backslash-then-dollar"),
    pytest.param("$5\n\n$ \\text{日本 語} $\n", id="currency-then-spaced-math"),
    pytest.param("$$\n日本 語\n=\n日本 語\n$$\n", id="display-math-with-setext-line"),
    *(
        pytest.param(
            f"$$\n\\text{{日本 語}}\n{line}\n\\text{{日本 語}}\n$$\n",
            id=f"display-math-with-{name}-line",
        )
        for name, line in [
            ("plus", "+ x"),
            ("minus", "- x"),
            ("heading", "# x"),
            ("quote", "> x"),
        ]
    ),
    pytest.param("価格は $5 と $10 です\n", id="currency-pair"),
    pytest.param(
        "$$\n\n日本 語\n\n    $$\n", id="display-math-closed-by-indented-code"
    ),
    pytest.param("$$\n\n日本 語\n\n<!-- $$ -->\n", id="display-math-closed-in-html"),
    # An unescaped `$` left in prose leaves the whole file unchanged.
    pytest.param("価格は $5 です\n\n日本 English\n", id="stray-dollar"),
    pytest.param("日本 English\n\n$$\n\n日本 English\n", id="unpaired-double-dollar"),
    pytest.param("$$\n\n    $$\n\n日本 English\n", id="double-dollar-then-indented"),
    pytest.param("記号 \\$$ と\n\n日本 English\n", id="escaped-then-bare-dollar"),
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


def test_format_text_repeats_until_nothing_changes(monkeypatch):
    """`format_text` repeats passes until one changes nothing.

    A stand-in pass that removes one space per call exercises the loop.
    """
    monkeypatch.setattr(
        markdown_cjk_latin_space_remover, "_pass", lambda text: text.replace(" ", "", 1)
    )
    assert format_text("a b c d\n") == "abcd\n"


def test_pass_raises_if_a_deletion_removes_a_non_space(monkeypatch):
    monkeypatch.setattr(
        markdown_cjk_latin_space_remover,
        "_delete",
        lambda src, positions: src.replace("本".encode(), b""),
    )
    with pytest.raises(RuntimeError, match="other than a space"):
        _pass("日本 English\n")


def test_deletions_raises_on_a_non_space_candidate():
    raw = "日 a".encode()
    # The space's span points at the bytes of "日".
    run = _Run(first=0, last=0, start=0, end=len(raw))
    run.chars = ["日", " ", "a"]
    run.spans = [(0, 3), (0, 3), (4, 5)]
    with pytest.raises(RuntimeError, match="is not a space"):
        _deletions(raw, [_Event("Text", "日 a", 0, len(raw))], run)


def test_runs_raises_on_overlapping_text():
    events = [
        _Event("Start", "Paragraph", 0, 6),
        _Event("Text", "abc", 0, 3),
        _Event("Text", "bc", 1, 3),
        _Event("End", "Paragraph", 0, 6),
    ]
    with pytest.raises(RuntimeError, match="overlapping"):
        _runs(b"abcdef", events)


def test_rejected_group_costs_logarithmic_parses(monkeypatch):
    """The shape-breaking groups among thousands are isolated by halving."""
    calls = 0
    parse = markdown_cjk_latin_space_remover._parse

    def counting_parse(text):
        nonlocal calls
        calls += 1
        return parse(text)

    monkeypatch.setattr(markdown_cjk_latin_space_remover, "_parse", counting_parse)
    body = "".join(f"段落 {i} の English テスト です。\n\n" for i in range(800))
    out = format_text("日本 **(a)** 語\n\n" + body)
    assert out.startswith("日本 **(a)** 語\n\n段落0のEnglishテストです。")
    assert calls < 100


@pytest.mark.parametrize(
    ("rejections", "tail"),
    [(-2, "日本English\n"), (0, "日本 English\n")],
    ids=["below-cap", "at-cap"],
)
def test_rejections_are_capped(rejections, tail):
    """After `_MAX_REJECTIONS` rejected groups, the groups not yet tried stay.

    Each `日本 **(a)** 語` paragraph holds two groups, both rejected; the
    `日本 English` group comes last.
    """
    cap = markdown_cjk_latin_space_remover._MAX_REJECTIONS
    head = "日本 **(a)** 語\n\n" * ((cap + rejections) // 2)
    assert format_text(head + "日本 English\n") == head + tail


def test_trailing_fold_does_not_reach_past_a_newline():
    """The trailing pattern matches at the end of the string only."""
    assert _TRAIL_CJK.search("日本 \n") is None
    assert _TRAIL_CJK.search("日本 ") is not None


@pytest.mark.parametrize(
    ("src", "folds"),
    [("日本 *a* 語", True), ("日本 _a_ 語", False), ("日本 __a__ 語", False)],
    ids=["asterisk", "underscore", "double-underscore"],
)
def test_emphasis_fold_depends_on_the_marker(src, folds):
    """`_deletions` folds next to `*` emphasis and not next to `_` emphasis."""
    text = src + "\n"
    events, raw = _parse(text), text.encode()
    positions = set().union(
        *(_deletions(raw, events, run) for run in _runs(raw, events))
    )
    assert bool(positions) is folds


# --- CLI ---------------------------------------------------------------------

CRLF_SRC = "日本 English\r\nテスト です\r\n".encode()
CRLF_OUT = "日本English\r\nテストです\r\n".encode()


def md_file(tmp_path, data, name="a.md"):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def changed_and_clean(tmp_path):
    return (
        md_file(tmp_path, CRLF_SRC, "changed.md"),
        md_file(tmp_path, CRLF_OUT, "clean.md"),
    )


def run_cli(*args, stdin=b"", cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "markdown_cjk_latin_space_remover", *args],
        input=stdin,
        capture_output=True,
        cwd=cwd,
    )


def test_cli_stdin_is_byte_exact():
    result = run_cli(stdin=CRLF_SRC)
    assert result.returncode == 0
    assert result.stdout == CRLF_OUT


def test_cli_file_to_stdout_is_byte_exact(tmp_path):
    path = md_file(tmp_path, CRLF_SRC)
    result = run_cli(str(path))
    assert result.stdout == CRLF_OUT
    assert path.read_bytes() == CRLF_SRC


def test_cli_in_place_is_byte_exact(tmp_path):
    path = md_file(tmp_path, CRLF_SRC)
    result = run_cli("-i", str(path))
    assert result.returncode == 0
    assert path.read_bytes() == CRLF_OUT


def test_cli_check(tmp_path):
    changed, clean = changed_and_clean(tmp_path)
    result = run_cli("--check", str(clean))
    assert result.returncode == 0
    assert result.stdout == b""
    result = run_cli("--check", str(changed))
    assert result.returncode == 1
    assert result.stdout.decode().splitlines() == [f"would reformat {changed}"]
    assert changed.read_bytes() == CRLF_SRC
    assert run_cli("--check", stdin=CRLF_SRC).returncode == 1
    assert run_cli("--check", stdin=CRLF_OUT).returncode == 0


def test_cli_file_to_stdout_prints_unchanged_files_too(tmp_path):
    path = md_file(tmp_path, CRLF_OUT)
    result = run_cli(str(path))
    assert result.returncode == 0
    assert result.stdout == CRLF_OUT


def test_cli_stdin_diff_keeps_line_endings():
    result = run_cli("--diff", stdin=CRLF_SRC)
    assert result.returncode == 0
    assert "-日本 English\r\n".encode() in result.stdout
    assert "+日本English\r\n".encode() in result.stdout


def test_cli_diff_keeps_line_endings(tmp_path):
    path = md_file(tmp_path, CRLF_SRC)
    result = run_cli("--diff", str(path))
    assert result.returncode == 0
    assert "-日本 English\r\n".encode() in result.stdout
    assert "+日本English\r\n".encode() in result.stdout
    assert path.read_bytes() == CRLF_SRC


def test_cli_in_place_leaves_unchanged_files_alone(tmp_path):
    changed, clean = changed_and_clean(tmp_path)
    result = run_cli("-i", str(changed), str(clean))
    assert result.returncode == 0
    assert result.stdout.decode().splitlines() == [f"reformatted {changed}"]
    assert changed.read_bytes() == CRLF_OUT
    assert clean.read_bytes() == CRLF_OUT


def test_cli_version():
    result = run_cli("-V")
    assert result.returncode == 0
    assert result.stdout.startswith(b"markdown-cjk-latin-space-remover ")


def test_cli_check_fails_if_any_file_would_change(tmp_path):
    changed, clean = changed_and_clean(tmp_path)
    assert run_cli("--check", str(changed), str(clean)).returncode == 1


def test_cli_diff_of_unchanged_file_is_empty(tmp_path):
    result = run_cli("--diff", str(md_file(tmp_path, CRLF_OUT)))
    assert result.returncode == 0
    assert result.stdout == b""


def test_cli_missing_file(tmp_path):
    result = run_cli(str(tmp_path / "missing.md"))
    assert result.returncode == 2
    assert b"not found" in result.stderr


def test_cli_directory(tmp_path):
    result = run_cli(str(tmp_path))
    assert result.returncode == 2
    assert b"is a directory" in result.stderr


def test_cli_reads_a_pipe_path():
    result = subprocess.run(
        f"{sys.executable} -m markdown_cjk_latin_space_remover <(printf '日本 English')",
        shell=True,
        executable="/bin/bash",
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout == "日本English".encode()


@pytest.mark.parametrize(
    "src",
    [
        "日本 English",
        "日本 English\r日本 English\n",
        "日本 English\f日本 English\n",
        "日本 English\u2028日本 English\n",
    ],
    ids=["no-final-newline", "lone-cr", "form-feed", "line-separator"],
)
def test_cli_diff_applies_with_git(tmp_path, src):
    path = md_file(tmp_path, src.encode(), "a.md")
    result = run_cli("--diff", "a.md", cwd=tmp_path)
    assert result.returncode == 0
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "apply", "-"], input=result.stdout, cwd=tmp_path, check=True)
    assert path.read_bytes() == format_text(src).encode()


def test_cli_ignores_in_place_on_stdin():
    result = run_cli("-i", stdin=CRLF_SRC)
    assert result.returncode == 0
    assert result.stdout == CRLF_OUT


def test_cli_in_place_writes_nothing_if_any_file_is_invalid(tmp_path):
    changed = md_file(tmp_path, CRLF_SRC, "changed.md")
    invalid = md_file(tmp_path, b"\xff", "invalid.md")
    assert run_cli("-i", str(changed), str(invalid)).returncode == 2
    assert changed.read_bytes() == CRLF_SRC


def test_cli_invalid_utf8(tmp_path):
    path = md_file(tmp_path, b"\xff\xfe")
    assert run_cli(str(path)).returncode == 2
    assert run_cli(stdin=b"\xff").returncode == 2


def test_cli_reports_an_internal_check_failure(monkeypatch, tmp_path, capsys):
    def failing_format_text(text):
        raise RuntimeError("an edit removed something other than a space")

    monkeypatch.setattr(
        markdown_cjk_latin_space_remover.__main__, "format_text", failing_format_text
    )
    path = md_file(tmp_path, CRLF_SRC)
    monkeypatch.setattr(
        sys, "argv", ["markdown-cjk-latin-space-remover", "--check", str(path)]
    )
    assert main() == 2
    assert "other than a space" in capsys.readouterr().err


def test_cli_reports_an_internal_check_failure_on_stdin(monkeypatch, capsys):
    def failing_format_text(text):
        raise RuntimeError("an edit removed something other than a space")

    monkeypatch.setattr(
        markdown_cjk_latin_space_remover.__main__, "format_text", failing_format_text
    )
    monkeypatch.setattr(sys, "argv", ["markdown-cjk-latin-space-remover", "--check"])
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(CRLF_SRC)))
    assert main() == 2
    assert "<stdin>" in capsys.readouterr().err


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read any file")
def test_cli_unreadable_file(tmp_path):
    path = md_file(tmp_path, CRLF_SRC)
    path.chmod(0)
    try:
        result = run_cli("--check", str(path))
    finally:
        path.chmod(0o600)
    assert result.returncode == 2
    assert b"Permission denied" in result.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root can write any file")
def test_cli_in_place_on_a_read_only_file(tmp_path):
    path = md_file(tmp_path, CRLF_SRC)
    path.chmod(0o444)
    try:
        result = run_cli("-i", str(path))
    finally:
        path.chmod(0o600)
    assert result.returncode == 2
    assert b"Permission denied" in result.stderr
    assert path.read_bytes() == CRLF_SRC


def test_cli_without_files_on_a_terminal(monkeypatch):
    class Terminal:
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "argv", ["markdown-cjk-latin-space-remover"])
    monkeypatch.setattr(sys, "stdin", Terminal())
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
