"""End-to-end tests: drive the plugin through mdformat as a user would.

Covers protected-span and boundary behaviour specific to the Markdown front-end.
The CJK-boundary cases marked `# MIRROR` have a paired Typst case in
typst-cjk-latin-space-remover's suite; keep the two in lockstep.
"""

import mdformat
from markdown_it import MarkdownIt


def fmt(md: str) -> str:
    return mdformat.text(md, extensions={"no_cjk_latin_space"})


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
