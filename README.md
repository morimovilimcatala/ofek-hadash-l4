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

The takanon collection also holds the conditions-of-service department's web
pages. They are not part of the takanon and are encoded as what they are:
the ministry's questions and answers as checks run against the takanon's
L4 (an answer the takanon contradicts, or a rule it adds where the takanon
is silent, is a finding), the introduction's precedence rule as a rule, and
the navigation pages as notes.

The collective agreements carry the rules the circulars price ("circulars
carry amounts; agreements carry rules"). Their collection is in work: every
agreement the corpus publishes has a page, and the base agreement of
25.12.2008 is read part by part and article by article, with its preamble
and its sign-off each a section of its own (`tools/akn.py`'s `SECTIONED`).
An agreement the corpus publishes without its text (an OCR layer it
refused) has nothing to encode until the corpus reads its pages.

## Layout

| Path | What |
|---|---|
| `corpus/` | read-only snapshot of the corpus's Akoma Ntoso (`SOURCE.toml` names the commit) and its document list |
| `l4/<corpus path>/<section>.l4` | one L4 file per section, laid out like the corpus |
| `conventions.toml`, `l4/conventions.l4` | the rules of reading the encoding follows where the text does not decide, and the one L4 definition of each that is a computation, which the rules import |
| `findings/<corpus path>/<section>.toml` (one per section) | errors in the text the encoding exposed, each backed by an `#ASSERT` |
| `data/calculator-delta.json` | the comparison with the ministry's salary simulator: inputs, outputs, mappings, clauses and classifications only (written outside this repository; shown as the simulator's group of the contradictions page) |
| `laws/<name>.toml`, `l4/laws/<name>.l4` | a statute encoded though the corpus holds no copy of it (חוק הסכמים קיבוציים, §§19–23): its sections' words pinned from ספר החוקים הפתוח, and their rules |
| `data/contradictions.json`, `data/contradictions/` | where one instrument contradicts another: a side per source (two or more), with a crop of each page, the rule that decides, and whether it was followed |
| `tools/` | the L4 runner, the AKN reader, the site generator |
| `toolchain/` | the pinned L4 compiler revision and its build script |
| `tests/` | alignment, coverage and evidence checks |

## Site

- **Documents** — documents → chapters → sections. The takanon has a
  contents page and a page per chapter, and so does the base agreement (a
  page per part); a circular is one page, and so is every other agreement
  and each of the department's web pages, listed under the takanon as a group of
  their own (in the sidebar, on the contents page and on the coverage page).
  The agreements are listed by family (the corpus's folders: Ofek Hadash, Oz
  LaTmura, the teachers' general agreements, the public-sector framework
  agreements), the circulars by school year. Each section
  is a two-column comparison, paragraph by paragraph: the text, and the L4
  that encodes it (switchable to `l4 render`'s natural-language rendering). The
  results of the file's `#EVAL`/`#ASSERT`/`#TRACE` sit under the code they test.
  Each obligation (`MUST`/`MAY`/`SHANT`) carries its state diagram, drawn by
  `l4 state-graph` and GraphViz (`dot`, which `make site` needs installed to
  draw them; without it the pages are built with no diagrams).
- **The sidebar** follows the page: on a document, its own chapter, year or
  family first and open, with an outline of the page, and the other collections
  closed below; on the findings page, every section and circular that has
  findings, with its count, following the filters; elsewhere, every
  collection.
- **Salary calculator** (`calculator.html`) — a form for §1.1's
  `salary of a teaching employee`: its fields and allowance kinds are read
  off the L4 file, and "חישוב" runs that file, with the form's values and an
  `#EVALTRACE` appended, through L4's own evaluator compiled to WebAssembly.
  It shows the total, each component with its clause, and the evaluation
  trace. Nothing in it re-implements a rule. §1.1 was last updated in 2010:
  from the month a later circular re-rates the 2008 or the 2011 supplement,
  the page marks that line as §1.1's figure and names the circular, and says
  the total is §1.1's alone (MMS-514).
- **The Collective Agreements Law** (`laws/collective-agreements-law.html`) —
  §§19–23, which say what an agreement's personal provisions are and which
  provision governs against a statute, a contract of employment or another
  agreement, encoded in L4 and set beside their text (MMS-516). The corpus
  keeps no copy of the law; the text is pinned in `laws/` from the live page.
  A circular whose rule pays less than the agreement it implements applies
  §22 through it (`l4/circulars/2008-09_tashsat_03.l4`).
- **Contradictions** (`contradictions.html`) — where one instrument says one
  thing and another says another about the same pay or right: an agreement
  and the circular that implements it, a circular and the letter it executes,
  two circulars, the takanon and a newer circular or agreement, a Q&A answer
  and the takanon, and a document and what is actually paid (MMS-515,
  MMS-517). A contradiction has a side per source that gives its own answer,
  two or more. Each shows a crop of
  every page — a scan's own pixels, a born-digital page rendered, or the saved
  web page as a browser draws it, captioned with file, page, resolution and
  pixel box, never resampled or retouched; the outline is drawn by the page
  over the picture — the rule that decides which side wins, quoted, and
  whether practice followed it — on the payslips (in general terms) and in
  the simulator, each its own filter, as is the kind
  of document. One whose rule was not followed is an error: it carries a
  severity grade, on the findings page's scale, and a "משמעות" paragraph on
  what it means for a teacher. The crops are cut
  outside this repository from the corpus repository's sources;
  `tests/test_contradictions.py` holds each quote to the corpus and each
  crop to its file.
  Its last group is **the simulator against the text** (MMS-522; until then a
  page of its own, `calculator-delta.html`, which now redirects there): where
  the Ministry of Education's public salary simulator computes otherwise than
  the text, grouped by cause (one rule, not one row per request), each cause
  quoting the clause that governs it and classified as the simulator departing
  from the text or a question both answers survive, with the simulator's own
  bugs; what was compared, and what was not, is folded under the heading. The
  group quotes the simulator's own disclaimer — it "מדמה שכר בלבד" and the
  ministry "אינו מתחייב לתשלום שכר על פי התחשיב" — so in every row the text
  governs. It is built from `data/calculator-delta.json`, which a comparison
  run outside this repository writes from a private extraction of the
  simulator (MMS-512, MMS-513), asking the L4 evaluator for every figure; the
  file holds no simulator code and no recorded traffic, and
  `tests/test_calculator_delta.py` holds it to that.
- **L4 findings** — what encoding found wrong in the law itself, by kind and
  by the stage that caught it (`findings.json` for machines), grouped by
  section or circular, folded to a title, and filterable by kind, stage,
  collection and words.
- **Conventions** (`conventions.html`) — the rules of reading the encoding
  follows where the text does not decide, each with the rules that apply it
  and the findings it decides. A convention that is a computation shows its
  definition in `l4/conventions.l4` beside the prose, with the `#ASSERT`s
  that pin it and the files that call it.
- **Coverage** — how much of the corpus is encoded, against the corpus's own
  document list.
- **Diagnostics** — the L4 checker's report, file by file.
- `index.json` — every L4 segment with the corpus address it encodes.

The site is in Hebrew, right to left (the client, 2026-10-10). The L4 code and the English prose `l4 render` writes from it are shown left to right; the findings are written in Hebrew; the one-line notes in the L4 source are English, as its identifiers are.

## Building

```sh
toolchain/build-l4.sh          # once: GHC 9.10.2 + cabal, builds `l4` (~30-60 min cold)
toolchain/build-wasm.sh        # only to rebuild the calculator's evaluator (see below)
make l4 site test
python3 -m http.server -d build/site
```

The working rules are in [CLAUDE.md](CLAUDE.md).

### The calculator's evaluator

`tools/assets/l4wasm/` holds `l4.wasm` (the L4 evaluator, `wasm-opt -Oz`)
and `l4.mjs` (GHC's JavaScript glue for it), committed so that the site
build needs no WASM toolchain. `BUILD.toml` beside them records what they
were built from: the commit in `toolchain/L4_COMMIT` plus
`toolchain/wasm-trace.patch`, with the sha256 of each file; a test fails if
either pin moves without a rebuild.

The patch is ours and is not upstream. It changes `jl4-core/src/L4/API.hs`
in two ways: an `#EVALTRACE` result in the evaluator's JSON carries its
trace (`trace`, a tree of steps and values, and `traceText`, the text `l4`
prints), where upstream drops it; and a new export, `l4_eval_files`, takes
the modules a source imports (here `common` and `conventions`), where
`l4_eval` resolves only the built-in libraries. `toolchain/build-wasm.sh` installs GHC's WASM
toolchain (ghc-wasm-meta at the commit in `toolchain/GHC_WASM_META`),
applies the patch at the pinned commit, builds, and rewrites the directory.
Bumping `L4_COMMIT` means re-running it, and checking the patch still applies.
