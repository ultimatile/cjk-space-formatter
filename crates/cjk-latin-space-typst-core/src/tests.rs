//! Cases marked `MIRROR` carry the same label in the two Markdown suites
//! (mdformat-no-cjk-latin-space's and markdown-cjk-latin-space-remover's);
//! keep the three in lockstep.

use super::*;

fn fmt(source: &str) -> String {
    format(source).unwrap()
}

#[track_caller]
fn check(cases: &[(&str, &str)]) {
    for (source, expected) in cases {
        assert_eq!(fmt(source), *expected, "source: {source:?}");
        assert_eq!(
            expected.replace(' ', ""),
            source.replace(' ', ""),
            "more than spaces changed: {source:?}"
        );
        assert_eq!(fmt(expected), *expected, "not idempotent: {source:?}");
    }
}

#[test]
fn prose_and_inline_spans() {
    check(&[
        ("テスト $x$ です", "テスト$x$です"), // MIRROR: inline math
        ("日本語 English テスト", "日本語Englishテスト"), // MIRROR: pure run
        ("Weyl chamber theorem", "Weyl chamber theorem"),
        (
            "パラメータは Weyl chamber $pi$ に制限できる。",
            "パラメータはWeyl chamber $pi$に制限できる。",
        ),
        ("純粋な日本語テキスト", "純粋な日本語テキスト"),
        ("行列 $A times.o B$ の", "行列$A times.o B$の"),
        ("$A$ と $B$ の積", "$A$と$B$の積"),
        ("これは `行 列` です", "これは`行 列`です"), // MIRROR: raw interior kept
        ("これは `code` です", "これは`code`です"),   // MIRROR: inline raw boundary
        ("", ""),
        ("テスト $x$ です\n", "テスト$x$です\n"),
        ("- $K$ ：1量子ビットゲート", "- $K$：1量子ビットゲート"),
        ("最大 3 個の", "最大3個の"), // MIRROR: pure run
        ("$U$ を", "$U$を"),
        ("Hello World", "Hello World"),
        ("テスト  $x$  です", "テスト$x$です"),
        ("= KAK（Weyl）分解", "= KAK（Weyl）分解"),
        ("注: これはテスト", "注: これはテスト"), // MIRROR: colon kept
        ("定義: 任意の $U$ を考える", "定義: 任意の$U$を考える"),
        ("日本語 *強調* です", "日本語*強調*です"),
        ("日本語 _em_ です", "日本語_em_です"),
        ("https://example.com 日本", "https://example.com日本"),
    ]);
}

#[test]
fn references_keep_the_space_that_ends_the_label() {
    check(&[
        ("式 @eq:fidelity の計算", "式@eq:fidelity の計算"),
        (
            "see @eq:fidelity for details",
            "see @eq:fidelity for details",
        ),
        ("参照 @eq:cost", "参照@eq:cost"),
        ("式 @eq:a と @eq:b を比較", "式@eq:a と@eq:b を比較"),
        ("メール @ 日本", "メール@ 日本"),
    ]);
}

#[test]
fn hash_expressions() {
    check(&[
        // The identifier would absorb the CJK text.
        ("#sym.ballot 基底状態", "#sym.ballot 基底状態"),
        ("#sym.icon.ballot 基底状態", "#sym.icon.ballot 基底状態"),
        ("#strong 太字テスト", "#strong 太字テスト"),
        (
            "+ #sym.ballot 基底状態の計算",
            "+ #sym.ballot 基底状態の計算",
        ),
        ("値は #x. 次に", "値は#x. 次に"),
        // A call ends at its closing delimiter.
        ("#text(red) 赤いテキスト", "#text(red)赤いテキスト"),
        (
            "#text(rgb(255, 0, 0)) 赤いテキスト",
            "#text(rgb(255, 0, 0))赤いテキスト",
        ),
        (r#"#text("C:\\") 日本語"#, r#"#text("C:\\")日本語"#),
        (
            r#"#text("say \"hi\"") テスト"#,
            r#"#text("say \"hi\"")テスト"#,
        ),
        ("#footnote[注] に", "#footnote[注]に"),
        // No space is next to a CJK character.
        ("#sym.ballot some text", "#sym.ballot some text"),
        ("#sym.ballot", "#sym.ballot"),
    ]);
}

#[test]
fn code_is_not_edited_but_content_blocks_are() {
    check(&[
        ("#let x = \"日本 語\"", "#let x = \"日本 語\""),
        ("#text(red)[日本 語 abc] 後 x", "#text(red)[日本語abc]後x"),
        ("#figure(supplement: [ 表 ])", "#figure(supplement: [表])"),
    ]);
}

#[test]
fn markers_follow_the_parser() {
    check(&[
        ("== 1. あ", "== 1.あ"),
        ("- 1. あわわわわ", "- 1. あわわわわ"),
        ("+ 1. あ", "+ 1. あ"),
        ("1. あわわわわ", "1. あわわわわ"),
        ("12. あ", "12. あ"),
        ("  - 1. あ", "  - 1. あ"),
        ("あ 1. ほげ", "あ1.ほげ"),
        ("Fig. 1. 図", "Fig. 1.図"),
        ("Step 1. 手順", "Step 1.手順"),
        ("v2. あ", "v2.あ"),
        ("Q1. 設問", "Q1.設問"),
        ("3.14. あ", "3.14.あ"),
        ("1.5 個", "1.5個"),
        ("Fig. 図", "Fig.図"),
        ("/ 用語 : 説明 abc", "/ 用語 : 説明abc"),
    ]);
}

#[test]
fn spaces_whose_removal_changes_the_tree_stay() {
    check(&[
        ("改行 \\ 次の行", "改行\\ 次の行"),
        ("データー *abc* です", "データー *abc*です"),
        ("温度は -5 度", "温度は -5度"),
        ("a - １", "a - １"),
        ("x < 最大値", "x < 最大値"),
    ]);
}

#[test]
fn a_space_before_a_quote_stays() {
    // Typst picks a quote's form from the character before it, which the
    // tree does not record. Only a quote right after the space is seen.
    check(&[
        ("これは 'a' です", "これは 'a'です"),
        ("日本語 \"abc\" です", "日本語 \"abc\"です"),
        ("これは *'a'* です", "これは*'a'*です"),
    ]);
}

#[test]
fn labels_do_not_hold_spaces() {
    check(&[
        ("日本 語 <l>", "日本語<l>"),
        ("重要 「注意」 <l>", "重要「注意」<l>"),
        ("= 導入 abc <sec>", "= 導入abc <sec>"),
    ]);
}

/// `fmt(source)`, and the bytes it parsed per byte of `source`.
fn parsed_per_byte(source: &str) -> (String, usize) {
    PARSED.with(|parsed| parsed.set(0));
    let out = fmt(source);
    (out, PARSED.with(|parsed| parsed.get()) / source.len())
}

#[test]
fn rejected_candidates_cost_a_line_each() {
    // Every `@ref` is followed by a candidate that changes the tree. Checked
    // on the whole text alone, each would cost a parse of all of it.
    let lines: String = (0..500).map(|i| format!("式 @eq:a{i} の計算\n")).collect();
    let expected = lines.replace("式 @", "式@");
    for (source, expected) in [
        (lines.clone(), expected.clone()),
        // Lines inside a content block count as lines too.
        (format!("#[\n{lines}]\n"), format!("#[\n{expected}]\n")),
        // A heading's text alone parses as a numbered-list item, so its candidates
        // are checked on the heading's line.
        (
            lines.replace("式 @", "= 1. 式 @"),
            expected.replace("式@", "= 1.式@"),
        ),
        // A lone `\r` ends a line too.
        (lines.replace('\n', "\r"), expected.replace('\n', "\r")),
    ] {
        let (out, per_byte) = parsed_per_byte(&source);
        assert_eq!(out, expected);
        assert!(per_byte < 20, "{per_byte} bytes parsed per byte");
    }
}

#[test]
fn comments_are_not_edited() {
    check(&[
        ("// 注 釈 abc\n本文 abc", "// 注 釈 abc\n本文abc"),
        (
            "/* 注 釈\n```\n*/ 外側 text です",
            "/* 注 釈\n```\n*/外側textです",
        ),
    ]);
}

#[test]
fn block_math() {
    check(&[
        ("$ U = e^(i phi) $ <kak>\n", "$ U = e^(i phi) $ <kak>\n"),
        (
            "テスト $x$ です\n$\n  content\n$ <label>\nテスト $y$ です\n",
            "テスト$x$です\n$\n  content\n$ <label>\nテスト$y$です\n",
        ),
        (
            "任意の2量子ビットユニタリゲート $U in S U(4)$ を以下のように分解する：\n",
            "任意の2量子ビットユニタリゲート$U in S U(4)$を以下のように分解する：\n",
        ),
        (
            "テスト\n$\n  V^T N V\n$ <euler-zyz>\n次の行\n",
            "テスト\n$\n  V^T N V\n$ <euler-zyz>\n次の行\n",
        ),
        (
            "$ a +\n  日 本\n$\n後 text\n",
            "$ a +\n  日 本\n$\n後text\n",
        ),
        ("$ x $ trailing\n後 text\n", "$ x $ trailing\n後text\n"),
        ("$ x = 1 $ という 式\n", "$ x = 1 $という式\n"),
        (
            "前 text\n$\n  A B\n$ <eq:fidelity>\n後 text\n",
            "前text\n$\n  A B\n$ <eq:fidelity>\n後text\n",
        ),
        (
            "Hello World\n$ x = 1 $\nfoo bar\n",
            "Hello World\n$ x = 1 $\nfoo bar\n",
        ),
        (
            "== 定義\n\n任意の $U$ を分解する。\n$ U = A B $ <def>\nここで $A$ は行列。\n",
            "== 定義\n\n任意の$U$を分解する。\n$ U = A B $ <def>\nここで$A$は行列。\n",
        ),
        // The close `$` ends a content line and a comment follows it.
        (
            "前 文\n$ a +\n  b $ <eq:x> // 注 釈 abc\n後 文 abc",
            "前文\n$ a +\n  b $ <eq:x> // 注 釈 abc\n後文abc",
        ),
    ]);
}

#[test]
fn block_raw() {
    check(&[
        (
            "```rust\nコード ブロック です\n```\n外側 text です\n",
            "```rust\nコード ブロック です\n```\n外側textです\n",
        ),
        ("```\n変換 されない\n```\n", "```\n変換 されない\n```\n"),
        (
            "前 text\n```\nそのまま です\n```\n後 text\n",
            "前text\n```\nそのまま です\n```\n後text\n",
        ),
        (
            "```py print(1) ```\n次 の行\n",
            "```py print(1) ```\n次の行\n",
        ),
        // The second fence line closes the first raw and opens another.
        (
            "```md\n```py inner ```\nCJK 内容 です\n```\n外側 text です\n",
            "```md\n```py inner ```\nCJK 内容 です\n```\n外側textです\n",
        ),
    ]);
}

#[test]
fn rejected_candidates_do_not_block_the_others() {
    // The candidates after `\` and before `-5` change the tree; the others on
    // the line do not.
    check(&[("一 二 三 \\ 四 五 六 -5 七 八", "一二三\\ 四五六 -5七八")]);
}

#[test]
fn passes_repeat_until_one_changes_nothing() {
    let one_space = |text: &str| {
        text.find(' ')
            .map(|i| format!("{}{}", &text[..i], &text[i + 1..]))
    };
    assert_eq!(fixpoint("a  b c".into(), one_space), "abc");
    assert_eq!(fixpoint("abc".into(), one_space), "abc");
}

#[test]
fn a_line_unchanged_since_an_earlier_pass_is_not_checked_again() {
    let text: String = (0..50).map(|i| format!("式 @eq:a{i} の計算\n")).collect();
    let mut memo = Memo::new();
    let measure = |memo: &mut Memo| {
        PARSED.with(|parsed| parsed.set(0));
        pass(&text, memo);
        PARSED.with(|parsed| parsed.get())
    };
    let first = measure(&mut memo);
    let again = measure(&mut memo);
    // Both rounds parse the text and each line once. Only the first also
    // parses each line with its candidate deleted.
    assert!(
        first - again >= text.len() / 2,
        "{again} bytes parsed again, {first} at first"
    );
}

#[test]
fn a_bom_is_kept_and_does_not_hide_the_first_line() {
    check(&[
        (
            "\u{feff}= 見出し abc\n本文 abc\n",
            "\u{feff}= 見出しabc\n本文abc\n",
        ),
        ("\u{feff}", "\u{feff}"),
    ]);
}

#[test]
fn line_endings_are_kept() {
    check(&[("行 一\r\n行 二 abc\r\n", "行一\r\n行二abc\r\n")]);
}

#[test]
fn syntax_errors_are_returned_with_their_lines() {
    let errors = format("本文 abc\n\n未閉 $ x の 計算 abc").unwrap_err();
    let lines: Vec<usize> = errors.iter().map(SyntaxError::line).collect();
    assert_eq!(lines, [3]);
    assert_eq!(errors.to_string(), "line 3: unclosed delimiter");

    let errors = format("\u{feff}#set heading(numbering: \"1.\") 見出し").unwrap_err();
    assert_eq!(
        errors.to_string(),
        "line 1: expected semicolon or line break"
    );

    // Typst also ends a line at a lone `\r`, and `\r\n` is one line break.
    let errors = format("a\r日本 abc\r$ x").unwrap_err();
    assert_eq!(errors.to_string(), "line 3: unclosed delimiter");
    let errors = format("a\r\n日本 abc\r\n$ x").unwrap_err();
    assert_eq!(errors.to_string(), "line 3: unclosed delimiter");

    let errors = format("#let\n\n#(1 +").unwrap_err();
    assert_eq!(
        errors.to_string(),
        "line 1: expected pattern; line 3: unclosed delimiter; line 3: expected expression"
    );
}
