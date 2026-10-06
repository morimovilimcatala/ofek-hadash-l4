# L4 · Ofek Hadash

The Ofek Hadash corpus — the instruments that govern Israeli teachers'
employment — encoded in [L4](https://legalese.com/l4/), and published as a
site that sets each section's text beside the rules read from it.

**Site:** https://morimovilimcatala.github.io/ofek-hadash-l4/
**Corpus:** https://morimovilimcatala.github.io/ofek-hadash-corpus/

The work starts with **תקנון שירות עובדי הוראה** (the teaching staff
service regulations), the one corpus document whose text is complete. Every
section is encoded, not only pay: eligibility, definitions, procedures, and
obligations as L4 regulative rules.

## Layout

| Path | What |
|---|---|
| `corpus/` | read-only snapshot of the corpus's Akoma Ntoso (`SOURCE.toml` names the commit) and its document list |
| `l4/<corpus path>/<section>.l4` | one L4 file per section, laid out like the corpus |
| `findings/<corpus path>/<section>.toml` (one per section) | errors in the text the encoding exposed, each backed by an `#ASSERT` |
| `tools/` | the L4 runner, the AKN reader, the site generator |
| `toolchain/` | the pinned L4 compiler revision and its build script |
| `tests/` | alignment, coverage and evidence checks |

## Site

- **Documents** — documents → chapters → sections. A section page is a
  two-column comparison, paragraph by paragraph: the text, and the L4 that
  encodes it (switchable to `l4 render`'s natural-language rendering). The
  results of the file's `#EVAL`/`#ASSERT`/`#TRACE` sit under the code they test.
- **L4 findings** — what encoding found wrong in the law itself, by kind and
  by the stage that caught it (`findings.json` for machines).
- **Coverage** — how much of the corpus is encoded, against the corpus's own
  document list.
- **Diagnostics** — the L4 checker's report, file by file.
- `index.json` — every L4 segment with the corpus address it encodes.

The site is in English; the corpus text is shown in Hebrew, as published.

## Building

```sh
toolchain/build-l4.sh          # once: GHC 9.10.2 + cabal, builds `l4` (~30-60 min cold)
make l4 site test
python3 -m http.server -d build/site
```

The working rules are in [CLAUDE.md](CLAUDE.md).
