"""End-to-end tests: drive the plugin through mdformat as a user would.

Covers protected-span and boundary behaviour specific to the Markdown front-end.
The CJK-boundary cases marked `# MIRROR` have a paired Typst case in
typst-cjk-latin-space-remover's suite; keep the two in lockstep.
"""

import mdformat


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
