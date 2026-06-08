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
and therefore free.

## Install & use

```sh
pip install mdformat-no-cjk-latin-space
mdformat your.md          # the plugin is auto-discovered once installed
```

## Behaviour & non-goals

- The half-width colon is preserved (`注: これは` stays), as correct prose typography.
- Spaces are folded across emphasis (`**…**` / `*…*`), links and images, but
  **not** across underscore emphasis (`_…_` / `__…__`): CommonMark forbids `_`
  from opening or closing intraword and CJK count as word characters, so dropping
  the space there would turn the markers literal. Use `*` for emphasis around CJK.
- The plugin runs under mdformat's default `wrap = "keep"`. With `wrap` set to
  `"no"` or a width, mdformat replaces spaces with internal wrap points before
  the plugin sees the text, so the plugin no-ops (it does not corrupt — it simply
  makes no change). Keep the default `wrap` to use this plugin.
- mdformat **re-formats the whole document**, not only the spaces this plugin
  targets. If you need surgical edits, this is not the right tool.
- Pathological inputs are out of scope; the parser's span model is the contract.
