"""Tests for cjk_space_formatter."""

import pytest

from cjk_space_formatter import format_line, format_text


class TestFormatLine:
    """Unit tests for single-line formatting."""

    def test_cjk_before_inline_math(self):
        assert format_line("テスト $x$ です") == "テスト$x$です"

    def test_cjk_before_english(self):
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

    def test_empty_line(self):
        assert format_line("") == ""

    def test_newline_preserved(self):
        assert format_line("テスト $x$ です\n") == "テスト$x$です\n"

    def test_typst_list_item(self):
        assert format_line("- $K$ ：1量子ビットゲート") == "- $K$：1量子ビットゲート"

    def test_number_adjacent_to_cjk(self):
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
        """Space after @label before ASCII is already safe, verify no regression."""
        assert (
            format_line("see @eq:fidelity for details")
            == "see @eq:fidelity for details"
        )

    def test_typst_ref_no_trailing_space(self):
        """@label at end of line (no trailing space) — nothing to protect."""
        assert format_line("参照 @eq:cost") == "参照@eq:cost"

    def test_half_width_colon_space_preserved(self):
        """Space after half-width colon before CJK must be preserved."""
        assert format_line("注: これはテスト") == "注: これはテスト"

    def test_half_width_colon_in_context(self):
        assert format_line("定義: 任意の $U$ を考える") == "定義: 任意の$U$を考える"

    def test_typst_ref_multiple(self):
        assert format_line("式 @eq:a と @eq:b を比較") == "式@eq:a と@eq:b を比較"

    def test_hash_space_before_cjk_preserved(self):
        """Space after # before CJK must be preserved (Markdown heading / Typst command)."""
        assert format_line("# ほげ") == "# ほげ"

    def test_multi_hash_heading_preserved(self):
        """Multi-level Markdown headings preserve space before CJK."""
        assert format_line("## セクション") == "## セクション"
        assert format_line("### 見出し") == "### 見出し"

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            # Simple and dotted identifiers
            ("#sym.ballot 基底状態", "#sym.ballot 基底状態"),
            ("#sym.icon.ballot 基底状態", "#sym.icon.ballot 基底状態"),
            ("#strong 太字テスト", "#strong 太字テスト"),
            # Parenthesised arguments (flat, nested, with strings)
            ("#text(red) 赤いテキスト", "#text(red) 赤いテキスト"),
            (
                "#text(rgb(255, 0, 0)) 赤いテキスト",
                "#text(rgb(255, 0, 0)) 赤いテキスト",
            ),
            (
                '#set heading(numbering: "1.") 見出し',
                '#set heading(numbering: "1.") 見出し',
            ),
            # Escaped backslashes / quotes inside strings
            (r'#text("C:\\") 日本語', r'#text("C:\\") 日本語'),
            (r'#text("say \"hi\"") テスト', r'#text("say \"hi\"") テスト'),
            # Before ASCII — space is already safe, must not break
            ("#sym.ballot some text", "#sym.ballot some text"),
            # Inside list item
            ("+ #sym.ballot 基底状態の計算", "+ #sym.ballot 基底状態の計算"),
            # No trailing space — nothing to protect
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
        """Typst hash expressions preserve the terminating space."""
        assert format_line(input_text) == expected

    @pytest.mark.parametrize(
        "input_text, expected",
        [
            ("Issue #123 の修正", "Issue #123の修正"),
            ("#123 バグ", "#123バグ"),
        ],
        ids=["mid-sentence", "standalone"],
    )
    def test_markdown_issue_ref_not_protected(self, input_text, expected):
        """Numeric #N tokens are not Typst expressions — space collapses normally."""
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
