# mdformat-no-cjk-latin-space

An [mdformat](https://github.com/hukkin/mdformat) plugin that removes unwanted
spaces between CJK characters and adjacent Latin letters or digits — the inverse
of CSS `text-autospace: ideograph-alpha`, which *inserts* such spacing. Where
pangu-style tools add spaces, this removes them.

```
日本語 English テスト   ->  日本語Englishテスト
行列 $x$ の計算          ->  行列$x$の計算
これは `code` です       ->  これは`code`です
```

## Why a plugin (not regex / textlint)

Math (`$...$`, `$$...$$`), inline code and fenced code must be protected from
edits. A plain Markdown AST has no math concept, so off-the-shelf textlint rules
cannot protect `$...$`. Building *on* mdformat instead, the framework
(mdformat + [dollarmath](https://github.com/executablebooks/mdit-py-plugins))
supplies CommonMark correctness and math node-isation; this plugin supplies only
the CJK-Latin logic. Protection of fences, code spans and escapes is structural
and therefore free — but only as far as the enabled extensions reach, which is
why [mdformat-gfm](https://github.com/hukkin/mdformat-gfm) is a hard dependency.

## Install & use

Not published to PyPI yet. Install from this repository:

```sh
pip install "git+https://github.com/ultimatile/cjk-space-formatter#subdirectory=packages/mdformat-no-cjk-latin-space"
mdformat your.md
```

`mdformat` with no `--extensions` selection enables every installed extension,
which is what you want here: this plugin plus the `gfm` and `tables` extensions
its dependency provides. If you narrow the set instead — `--extensions`, an
`extensions` key in `.mdformat.toml`, or the `extensions=` argument in the
Python API — name all three, or GFM task lists, autolink literals and tables
lose their protection:

```python
mdformat.text(src, extensions={"no_cjk_latin_space", "gfm", "tables"})
```

## Behaviour & non-goals

- The half-width colon is preserved (`注: これは` stays), as correct prose typography.
- Spaces are folded across emphasis (`**…**` / `*…*`), links, images and
  strikethrough (`~~…~~`), but **not** across underscore emphasis (`_…_` /
  `__…__`): CommonMark forbids `_` from opening or closing intraword and CJK
  count as word characters, so dropping the space there would turn the markers
  literal. Use `*` for emphasis around CJK.
- **Known gap:** folding is currently one-sided — a CJK-adjacent space is removed
  only when the CJK is in the surrounding text run, not when it sits *inside*
  emphasis/link markup, so `Foo **設定** bar` keeps its spaces. This is an
  incomplete realization of the CJK-ambient rule (not an intentional asymmetry);
  it rarely bites genuinely CJK-ambient text.
- A CJK heading's generated anchor id follows the squashed text, so `## 見出し です`
  becomes id `見出しです` while a link written as `[…](#見出し-です)` still points at
  the old slug. Update in-document anchor links after the first run.
- The plugin runs under mdformat's default `wrap = "keep"`. With `wrap` set to
  `"no"` or a width, mdformat replaces spaces with internal wrap points before
  the plugin sees the text, so the plugin no-ops (it does not corrupt — it simply
  makes no change). Keep the default `wrap` to use this plugin.
- mdformat **re-formats the whole document**, not only the spaces this plugin
  targets. If you need surgical edits, this is not the right tool.
- Pathological inputs are out of scope; the parser's span model is the contract.
