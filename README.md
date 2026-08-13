# cjk-latin-space

Tools that **remove** unwanted spaces between CJK characters and adjacent
Latin letters, digits, or math — the spaces LLMs tend to insert when they carry
English spacing conventions into Japanese text. This is the inverse of CSS
`text-autospace: ideograph-alpha` and of pangu-style tools, which *add* such
spacing.

```
任意の2量子ビットユニタリゲート $U in S U(4)$ を分解する
->  任意の2量子ビットユニタリゲート$U in S U(4)$を分解する
```

## Scope: CJK-ambient text

These tools assume the surrounding text is **CJK-ambient** — Japanese (or other
CJK) prose with the occasional Latin word, math, or code. Under that assumption
every space adjacent to a CJK character is unwanted and removed. If your document
is *Latin-ambient* — English prose with the occasional CJK word — you do not want
this tool: there the spaces are correct Latin word separation. The tools do not
detect ambient language; feeding them Latin-ambient text will strip spaces that
should stay.

## Which tool do you want?

The spaces are easy; the hard part is **not touching** math, code, and other
spans where a space is meaningful. Markdown and Typst protect different spans in
different ways, so this repo ships **two** tools rather than one tool that half-
serves both:

| You edit…    | Use                                                                       | Form            | Status      |
| ------------ | ------------------------------------------------------------------------- | --------------- | ----------- |
| **Markdown** | [`mdformat-no-cjk-latin-space`](packages/mdformat-no-cjk-latin-space)     | mdformat plugin | usable      |
| **Typst**    | [`typst-cjk-latin-space-remover`](packages/typst-cjk-latin-space-remover) | standalone CLI  | provisional |

Each package's README has install and usage. Neither is on PyPI; both install
from this repository.

The Markdown tool builds on mdformat + dollarmath, so fence/code/math protection
is structural (the parser never exposes their interior) for every construct an
enabled extension parses — which is why it depends on mdformat-gfm rather than
leaving GFM constructs to chance.

The Typst tool is a self-contained CLI with a regex/state-machine scanner for
Typst's spans (`$`, `` ` ``, `#expr`, `@ref`, list markers). It is
**provisional** — that scanner has limits its README lists, and the package is
not released while they stand.

## Migrating from `cjk-space-formatter`

The single `cjk-space-formatter` CLI that handled both formats is **deprecated**
in favour of the two tools above. For Markdown, install the plugin and run
`mdformat`. For Typst, `typst-cjk-latin-space-remover file.typ` replaces
`cjk-space-formatter file.typ`, subject to the provisional status above.

## Repository layout

```
packages/
  mdformat-no-cjk-latin-space/    # published from here; not on PyPI yet
  typst-cjk-latin-space-remover/  # provisional, unreleased
core/                             # cjk-latin-space core: squash(plain_run) — build-time vendored, not published
conformance/                      # pure-run core corpus, target-independent
```

The shared core holds only the format-independent invariant — collapsing
CJK<->Latin/digit spaces within a plain run (with the half-width colon as the
sole exception). Span/boundary protection is each tool's own plumbing. The core
is vendored into each wheel at build time, so it is never a runtime dependency
and the two packages release independently.

## Alternatives

Several tools touch CJK / half-width spacing; they differ by **direction** (add
vs remove) and **target**:

| Tool                                                                                                                          | Direction                                  | Target                             |
| ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------- |
| [pangu](https://github.com/vinta/pangu.js)                                                                                    | adds spaces                                | HTML / plain text (not for markup) |
| [Prettier](https://github.com/prettier/prettier/issues/6385)                                                                  | adds in Markdown by default (configurable) | code / Markdown                    |
| [textlint](https://github.com/textlint/textlint) + [textlint-plugin-typst](https://github.com/textlint/textlint-plugin-typst) | removes (`--fix`able)                      | Markdown / Typst / text            |
| **this repo**                                                                                                                 | removes                                    | Markdown / Typst source            |

Off-the-shelf textlint rules cannot protect `$...$`: a plain Markdown AST has no
math concept. These tools solve that by owning the math/span model — the Markdown
plugin via dollarmath, the Typst CLI via its own scanner.

## Development

```bash
uv sync                       # installs both packages + core (editable) and pytest
uv run pytest conformance packages
```

The core is resolved from the editable workspace install during development, so
edits to `core/` take effect immediately without rebuilding the vendored copy.
