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
        text = "任意の2量子ビットユニタリゲート $U in S U(4)$ を以下のように分解する：\n"
        expected = "任意の2量子ビットユニタリゲート$U in S U(4)$を以下のように分解する：\n"
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
            "== 定義\n"
            "\n"
            "任意の$U$を分解する。\n"
            "$ U = A B $ <def>\n"
            "ここで$A$は行列。\n"
        )
        assert format_text(text) == expected
