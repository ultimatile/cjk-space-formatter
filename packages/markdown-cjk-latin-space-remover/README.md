# markdown-cjk-latin-space-remover

A CLI that removes the spaces next to CJK characters in Markdown files: a run
of spaces between two non-space characters goes when either side is CJK,
except a space right after a half-width colon. This is the inverse of CSS
`text-autospace: ideograph-alpha`, which *inserts* spacing between CJK and
Latin text.

```
日本語 English テスト   ->  日本語Englishテスト
行列 $x$ の計算          ->  行列$x$の計算
これは `code` です       ->  これは`code`です
```

## Only the spaces change

The output is the input with some spaces deleted. Every other byte is
unchanged, including line endings and HTML. A deletion is kept only if
pulldown-cmark parses the result to the same structure; for example, the
spaces around `**(a)**` next to CJK stay. Code, math, front matter, and bare
URLs keep their spaces.

A space at the edge of the prose folds into an adjacent code span, math, link,
image, strikethrough, or `*` emphasis (`日本語 **English** テスト` ->
`日本語**English**テスト`). It does not fold into `_` emphasis; use `*` for
emphasis around CJK.

## Which Markdown it reads

Files are read the way [pulldown-cmark](https://github.com/pulldown-cmark/pulldown-cmark)
reads them: CommonMark with tables, strikethrough, task lists, `$` / `$$`
math, and `---` YAML / `+++` TOML front matter. Markdown dialects such as
Slidev or Obsidian are not modelled; where a dialect reads a construct
differently, the edits follow pulldown-cmark's reading.

If a `$` in the prose is neither math nor escaped as `\$` (for example
`$5`), the file is left unchanged. Write a literal dollar sign as `\$`.

[`mdformat-no-cjk-latin-space`](../mdformat-no-cjk-latin-space) is the mdformat
plugin for repositories that format their Markdown with mdformat, which
re-formats the whole document.

## Install & use

Not published to PyPI yet. Install from this repository:

```sh
pip install "git+https://github.com/ultimatile/cjk-space-formatter#subdirectory=packages/markdown-cjk-latin-space-remover"
markdown-cjk-latin-space-remover -i your.md     # edit in place
cat your.md | markdown-cjk-latin-space-remover  # stdin -> stdout
```

`--check` exits non-zero if a file would change; `--diff` shows a unified diff.
From Python, `format_text(text)` returns the formatted string.

## Non-goals

- The half-width colon is preserved (`注: これは`).
- A CJK word *inside* emphasis or a link keeps the spaces around it:
  `Foo **設定** bar` is unchanged
  ([#9](https://github.com/ultimatile/cjk-space-formatter/issues/9)).
- Headings are edited like other prose; links to their generated anchors
  (`[…](#見出し-です)`) are not.
- Text between two top-level `---` lines may be parsed as front matter and left
  unedited.
