# markdown-cjk-latin-space-remover

A CLI that removes unwanted spaces between CJK characters and adjacent Latin
letters or digits in Markdown files — the inverse of CSS
`text-autospace: ideograph-alpha`, which *inserts* such spacing.

```
日本語 English テスト   ->  日本語Englishテスト
行列 $x$ の計算          ->  行列$x$の計算
これは `code` です       ->  これは`code`です
```

## Only the spaces change

The file is parsed for byte positions and never re-rendered: the output is the
input with some spaces deleted, byte for byte otherwise. Markdown dialects whose
syntax a CommonMark renderer would rewrite — [Slidev](https://sli.dev/)'s
per-slide front matter, HTML blocks, Vue components — pass through untouched,
and so do line endings.

[`mdformat-no-cjk-latin-space`](../mdformat-no-cjk-latin-space) removes the same
spaces as an mdformat plugin, which re-formats the whole document; use it when
the repository already formats its Markdown with mdformat.

## Protected spans

These keep every space they contain, and the spaces touching them where noted:

- code spans, fenced and indented code, and inline / display math
- front matter (`---` YAML and `+++` TOML blocks, also mid-document)
- bare URLs and email addresses, including the spaces on either side — GitHub
  would otherwise read the following CJK as part of the link
- the label of a `[label]` or `[label][]` reference link, which must keep
  matching its definition
- any top-level block containing a `$` that is not parsed as math, and anything
  between two `$$` that are not parsed as math: another renderer may still read
  math there

A space at the edge of the prose folds into an adjacent code span, math, link,
image, strikethrough, or `*` emphasis (`日本語 **English** テスト` ->
`日本語**English**テスト`). It does not fold into `_` emphasis: CommonMark forbids
`_` from opening or closing intraword and CJK count as word characters, so
dropping the space would make the markers literal. Use `*` for emphasis around
CJK.

A removal that would change how the document parses — for example one that
turns `**(a)**` next to CJK into literal asterisks — is not made.

## Install & use

Not published to PyPI yet. Install from this repository:

```sh
pip install "git+https://github.com/ultimatile/cjk-space-formatter#subdirectory=packages/markdown-cjk-latin-space-remover"
markdown-cjk-latin-space-remover -i your.md     # edit in place
cat your.md | markdown-cjk-latin-space-remover  # stdin -> stdout
```

`--check` exits non-zero if a file would change; `--diff` shows a unified diff.
From Python, `format_text(text)` returns the formatted string; there is no
file-level helper, because reading through text mode would rewrite line
endings.

## Non-goals

- The half-width colon is preserved (`注: これは`).
- A CJK word *inside* emphasis or a link keeps the spaces around it:
  `Foo **設定** bar` is unchanged
  ([#9](https://github.com/ultimatile/cjk-space-formatter/issues/9)).
- A CJK heading's generated anchor id follows the squashed text, so a link to
  the old slug (`[…](#見出し-です)`) needs updating after the first run.
- A `---` line after a blank line, directly followed by text, can open front
  matter when another `---` line follows later; prose between two such lines is
  left alone.
- Pathological inputs, such as a bare URL containing `$x$`, are out of scope.
