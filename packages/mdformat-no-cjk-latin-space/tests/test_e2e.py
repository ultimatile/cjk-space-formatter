"""End-to-end tests: drive the plugin through mdformat as a user would.

Covers protected-span and boundary behaviour specific to the Markdown front-end.
The CJK-boundary cases marked `# MIRROR` have a paired Typst case in
typst-cjk-latin-space-remover's suite; keep the two in lockstep.
"""

import mdformat
import pytest
from markdown_it import MarkdownIt
from mdit_py_plugins.gfm_autolink import gfm_autolink_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

# The set the package ships: `gfm` and `tables` come from the mdformat-gfm
# dependency, and without them GFM constructs reach the plugin as paragraph text
# and lose the spaces their syntax uses as delimiters.
SHIPPED_EXTENSIONS = {"no_cjk_latin_space", "gfm", "tables"}


def fmt(md: str) -> str:
    return mdformat.text(md, extensions=SHIPPED_EXTENSIONS)


def render_gfm(md: str) -> str:
    """Render as GFM, to assert a construct still means what it looked like.

    Asserting only on the formatted source would pass just as well if the plugin
    stopped doing anything, so the GFM cases below check the rendering too.
    Task lists and bare-URL autolinks need their plugins registered explicitly;
    `linkify` stays off because linkify-it-py is not a dependency.
    """
    parser = MarkdownIt("gfm-like", {"linkify": False})
    return parser.use(tasklists_plugin).use(gfm_autolink_plugin).render(md)


def test_fold_across_code_inline():  # MIRROR: inline raw
    assert fmt("これは `code` です\n") == "これは`code`です\n"


def test_inline_math_boundary():  # MIRROR: inline math
    assert fmt("行列 $x$ の計算\n") == "行列$x$の計算\n"


def test_code_interior_preserved():  # MIRROR: raw interior kept
    assert fmt("これは `行 列` です\n") == "これは`行 列`です\n"


def test_run_cjk_latin():  # MIRROR: pure run
    assert fmt("日本語 English テスト\n") == "日本語Englishテスト\n"


def test_run_cjk_digit():  # MIRROR: pure run
    assert fmt("最大 3 個の項目\n") == "最大3個の項目\n"


def test_colon_exception():  # MIRROR: colon kept
    assert fmt("注: これはテスト\n") == "注: これはテスト\n"


def test_fence_interior_untouched():
    """Fenced code is kept out of text nodes by the parser — never touched."""
    src = "```\nコード ブロック です\n```\n"
    assert fmt(src) == src


def test_block_math_boundary():
    assert fmt("式は\n\n$$\nx = 1\n$$\n\nです\n") == "式は\n\n$$\nx = 1\n$$\n\nです\n"


def test_labelled_block_math_round_trips():
    """dollarmath runs with labels on, so `$$ … $$ (eq)` is its own token type."""
    src = "式は\n\n$$\nx = 1\n$$ (eq)\n\nです\n"
    assert fmt(src) == src


def test_pure_ascii_unchanged():
    assert fmt("Hello World\n") == "Hello World\n"


def test_fold_across_asterisk_strong():
    assert fmt("日本語 **English** テスト\n") == "日本語**English**テスト\n"


def test_fold_across_asterisk_em():
    assert fmt("日本語 *English* テスト\n") == "日本語*English*テスト\n"


def test_underscore_emphasis_preserved():
    """Folding underscore emphasis would make the markers literal — so don't.

    CommonMark forbids `_`/`__` from opening/closing intraword and CJK count as
    word characters; `日本語_English_テスト` renders the underscores literally.
    The space is therefore kept, unlike asterisk emphasis which folds safely.
    """
    assert fmt("日本語 _English_ テスト\n") == "日本語 _English_ テスト\n"
    assert fmt("日本語 __English__ テスト\n") == "日本語 __English__ テスト\n"


def test_folded_asterisk_emphasis_still_renders():
    """Safety invariant: folding must not break the emphasis it folds across."""
    rendered = MarkdownIt().render(fmt("日本語 **English** テスト\n"))
    assert "<strong>English</strong>" in rendered


def test_fold_across_link():
    assert fmt("日本語 [English](x) テスト\n") == "日本語[English](x)テスト\n"


def test_fold_across_image():
    assert fmt("日本語 ![alt](x) テスト\n") == "日本語![alt](x)テスト\n"


def test_fold_across_strikethrough():
    """Both boundary edges: `_TRAIL_CJK` before `~~` and `_LEAD_CJK` after it."""
    assert fmt("日本語 ~~English~~ テスト\n") == "日本語~~English~~テスト\n"


def test_folded_strikethrough_still_renders():
    assert "<s>English</s>" in render_gfm(fmt("日本語 ~~English~~ テスト\n"))


@pytest.mark.parametrize(
    "src, expected",
    [
        ("> 日本語 English\n", "> 日本語English\n"),
        ("> > 日本語 English\n", "> > 日本語English\n"),
        (">日本語 English\n", "> 日本語English\n"),
        ("> 日本語 English\n続き です\n", "> 日本語English\n> 続きです\n"),
        ("> Plain English text\n", "> Plain English text\n"),
    ],
    ids=["single", "nested", "no-space-marker", "lazy-continuation", "latin-only"],
)
def test_blockquote_marker_padding_survives(src, expected):
    """The padding after `>` is markup, not prose, so the squash must miss it.

    markdown-it puts the marker in `blockquote_open`, leaving the inline token
    with content alone, so the postprocessor never sees it.
    """
    assert fmt(src) == expected


def test_task_list_checkbox_survives():
    assert fmt("- [ ] 項目 A\n- [x] 完了 した\n") == "- [ ] 項目A\n- [x] 完了した\n"
    assert 'type="checkbox"' in render_gfm(fmt("- [ ] 項目 A\n"))


def test_autolink_literal_survives():
    src = "詳細は https://example.com を参照\n"
    assert fmt(src) == src
    assert 'href="https://example.com"' in render_gfm(fmt(src))


def test_table_padding_survives_and_cell_squashes():
    formatted = fmt("| 列 | Name |\n| --- | --- |\n| 日本 語 | x |\n")
    assert "| 日本語 |" in formatted
    assert "<table>" in render_gfm(formatted)


@pytest.mark.parametrize(
    "src",
    [
        "日本語 English テスト\n",
        "- [ ] 項目 A\n",
        "| 列 |\n| --- |\n| 日本 語 |\n",
        "日本語 ~~English~~ テスト\n",
        "> 日本語 English\n",
    ],
    ids=["run", "task-list", "table", "strikethrough", "blockquote"],
)
def test_idempotent(src):
    once = fmt(src)
    assert fmt(once) == once
