"""Tests for typst-cjk-latin-space-remover.

Inherits the Typst-relevant pinned behaviour of the legacy single-tool suite
(Markdown-heading-specific cases dropped — this front-end is Typst-only) and
adds inline/block raw protection. Cases marked `# MIRROR` pair with a Markdown
case in mdformat-no-cjk-latin-space's suite; keep the pair in lockstep.
"""

import pytest

from typst_cjk_latin_space_remover import format_line, format_text


class TestFormatLine:
    """Unit tests for single-line formatting."""

    def test_cjk_before_inline_math(self):  # MIRROR: inline math
        assert format_line("テスト $x$ です") == "テスト$x$です"

    def test_cjk_before_english(self):  # MIRROR: pure run
        assert format_line("日本語 English テスト") == "日本語Englishテスト"

    def test_english_spaces_preserved(self):
        assert format_line("Weyl chamber theorem") == "Weyl chamber theorem"

    def test_mixed_cjk_english_math(self):
        assert (
            format_line("パラメータは Weyl chamber $pi$ に制限できる。")
            == "パラメータはWeyl chamber $pi$に制限できる。"
        )

    def test_no_change_needed(self):
        assert format_line("純粋な日本語テキスト") == "純粋な日本語テキスト"

    def test_math_content_preserved(self):
        assert format_line("行列 $A times.o B$ の") == "行列$A times.o B$の"

    def test_multiple_math_blocks(self):
        assert format_line("$A$ と $B$ の積") == "$A$と$B$の積"

    def test_inline_raw_interior_preserved(self):  # MIRROR: raw interior kept
        assert format_line("これは `行 列` です") == "これは`行 列`です"

    def test_inline_raw_boundary_folded(self):  # MIRROR: inline raw boundary
        assert format_line("これは `code` です") == "これは`code`です"

    def test_empty_line(self):
        assert format_line("") == ""

    def test_newline_preserved(self):
        assert format_line("テスト $x$ です\n") == "テスト$x$です\n"

    def test_typst_list_item(self):
        assert format_line("- $K$ ：1量子ビットゲート") == "- $K$：1量子ビットゲート"

    def test_number_adjacent_to_cjk(self):  # MIRROR: pure run
        assert format_line("最大 3 個の") == "最大3個の"

    def test_cjk_punctuation_after_math(self):
        assert format_line("$U$ を") == "$U$を"

    def test_pure_ascii_unchanged(self):
        assert format_line("Hello World") == "Hello World"

    def test_multiple_spaces_collapsed(self):
        assert format_line("テスト  $x$  です") == "テスト$x$です"

    def test_heading_line(self):
        assert format_line("= KAK（Weyl）分解") == "= KAK（Weyl）分解"

    def test_typst_ref_space_preserved(self):
        """Space after @label terminates the reference — must not be removed."""
        assert format_line("式 @eq:fidelity の計算") == "式@eq:fidelity の計算"

    def test_typst_ref_ascii_after(self):
        assert (
            format_line("see @eq:fidelity for details")
            == "see @eq:fidelity for details"
        )

    def test_typst_ref_no_trailing_space(self):
        assert format_line("参照 @eq:cost") == "参照@eq:cost"

    def test_half_width_colon_space_preserved(self):  # MIRROR: colon kept
        assert format_line("注: これはテスト") == "注: これはテスト"

    def test_half_width_colon_in_context(self):
        assert format_line("定義: 任意の $U$ を考える") == "定義: 任意の$U$を考える"

    def test_typst_ref_multiple(self):
        assert format_line("式 @eq:a と @eq:b を比較") == "式@eq:a と@eq:b を比較"

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("#sym.ballot 基底状態", "#sym.ballot 基底状態"),
            ("#sym.icon.ballot 基底状態", "#sym.icon.ballot 基底状態"),
            ("#strong 太字テスト", "#strong 太字テスト"),
            ("#text(red) 赤いテキスト", "#text(red) 赤いテキスト"),
            (
                "#text(rgb(255, 0, 0)) 赤いテキスト",
                "#text(rgb(255, 0, 0)) 赤いテキスト",
            ),
            (
                '#set heading(numbering: "1.") 見出し',
                '#set heading(numbering: "1.") 見出し',
            ),
            (r'#text("C:\\") 日本語', r'#text("C:\\") 日本語'),
            (r'#text("say \"hi\"") テスト', r'#text("say \"hi\"") テスト'),
            ("#sym.ballot some text", "#sym.ballot some text"),
            ("+ #sym.ballot 基底状態の計算", "+ #sym.ballot 基底状態の計算"),
            ("#sym.ballot", "#sym.ballot"),
        ],
        ids=[
            "dotted",
            "multi-dotted",
            "simple-ident",
            "parens",
            "nested-parens",
            "keyword-string-args",
            "escaped-backslash",
            "escaped-quote",
            "before-ascii",
            "in-list",
            "no-trailing-space",
        ],
    )
    def test_typst_hash_expr(self, input_text, expected):
        assert format_line(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            # Ordered-list markers preceding CJK keep their trailing space at a
            # structural position: line start, optionally behind Typst heading /
            # bullet prefixes (=, - +), including indentation.
            ("== 1. あ", "== 1. あ"),
            ("- 1. あわわわわ", "- 1. あわわわわ"),
            ("+ 1. あ", "+ 1. あ"),
            ("1. あわわわわ", "1. あわわわわ"),
            ("12. あ", "12. あ"),
            ("  - 1. あ", "  - 1. あ"),
            # Non-structural positions are ordinary text: collapse before CJK.
            ("あ 1. ほげ", "あ1.ほげ"),
            ("Fig. 1. 図", "Fig. 1.図"),
            ("Step 1. 手順", "Step 1.手順"),
            ("v2. あ", "v2.あ"),
            ("Q1. 設問", "Q1.設問"),
            ("3.14. あ", "3.14.あ"),
            ("1.5 個", "1.5個"),
            ("Fig. 図", "Fig.図"),
        ],
        ids=[
            "typst-heading-nested",
            "bullet-nested",
            "plus-bullet-nested",
            "line-start",
            "multi-digit",
            "indented-nested",
            "mid-line",
            "prose-figure-number",
            "prose-step-number",
            "version-string",
            "label-Q1",
            "multi-dot",
            "decimal",
            "non-digit-period",
        ],
    )
    def test_ordered_marker_space(self, input_text, expected):
        assert format_line(input_text) == expected


class TestFormatText:
    """Integration tests for multi-line text formatting."""

    def test_single_line_block_math_skipped(self):
        text = "$ U = e^(i phi) $ <kak>\n"
        assert format_text(text) == text

    def test_multiline_block_math_skipped(self):
        text = "テスト $x$ です\n$\n  content\n$ <label>\nテスト $y$ です\n"
        expected = "テスト$x$です\n$\n  content\n$ <label>\nテスト$y$です\n"
        assert format_text(text) == expected

    def test_real_world_line(self):
        text = (
            "任意の2量子ビットユニタリゲート $U in S U(4)$ を以下のように分解する：\n"
        )
        expected = (
            "任意の2量子ビットユニタリゲート$U in S U(4)$を以下のように分解する：\n"
        )
        assert format_text(text) == expected

    def test_block_math_with_hyphenated_label(self):
        text = "テスト\n$\n  V^T N V\n$ <euler-zyz>\n次の行\n"
        expected = "テスト\n$\n  V^T N V\n$ <euler-zyz>\n次の行\n"
        assert format_text(text) == expected

    def test_block_math_with_colon_label_resumes(self):
        """A colon in the close label must still be recognised as the closer.

        Typst labels routinely carry colons (`<eq:fidelity>`, matching `@eq:…`
        refs). If the closer is missed, every later line stays stuck inside the
        block-math state and is never formatted.
        """
        text = "前 text\n$\n  A B\n$ <eq:fidelity>\n後 text\n"
        expected = "前text\n$\n  A B\n$ <eq:fidelity>\n後text\n"
        assert format_text(text) == expected

    def test_no_cjk_text_unchanged(self):
        text = "Hello World\n$ x = 1 $\nfoo bar\n"
        assert format_text(text) == text

    def test_empty_text(self):
        assert format_text("") == ""

    def test_mixed_lines(self):
        text = (
            "== 定義\n"
            "\n"
            "任意の $U$ を分解する。\n"
            "$ U = A B $ <def>\n"
            "ここで $A$ は行列。\n"
        )
        expected = (
            "== 定義\n\n任意の$U$を分解する。\n$ U = A B $ <def>\nここで$A$は行列。\n"
        )
        assert format_text(text) == expected

    def test_block_raw_interior_skipped(self):
        """Raw block content is kept verbatim — CJK spaces inside are untouched."""
        text = "```rust\nコード ブロック です\n```\n外側 text です\n"
        expected = "```rust\nコード ブロック です\n```\n外側textです\n"
        assert format_text(text) == expected

    def test_block_raw_no_lang(self):
        text = "```\n変換 されない\n```\n"
        assert format_text(text) == text

    def test_block_raw_then_resume(self):
        """Formatting resumes after the closing fence."""
        text = "前 text\n```\nそのまま です\n```\n後 text\n"
        expected = "前text\n```\nそのまま です\n```\n後text\n"
        assert format_text(text) == expected
