# Working rules for this repo

This repository encodes the Ofek Hadash corpus in L4 and publishes a site
that sets each section's TEXT beside its L4. The text is the corpus's; the
reading of it is ours. Use the L4 skill (`writing-l4-rules`, from
legalese/l4-ide `skills/`) for anything about the language.

## The corpus decides the text

- `corpus/` is a vendored snapshot of `morimovilimcatala/TeachersSalaryCatala`
  `akn/` (`corpus/SOURCE.toml` names the commit). It is never edited here.
  A defect in the text as the corpus publishes it — a lost table, a wrong
  date — is the corpus's to fix: file it there (Linear team `MMS`, project
  `AKN corpus`), then re-sync with `tools/sync_corpus.py`.
- **The L4 reads the corpus text, never the PDF or the source document**
  (the client, 2026-10-07). A page may be opened to UNDERSTAND a garbled
  row or to confirm a finding, but what the L4 encodes is what the corpus
  publishes. Where the page shows the corpus is wrong, missing or
  scrambled, that is a corpus issue: file it in Linear (`AKN corpus`) with
  what the page shows. The L4 takes the affected value as a named input
  until the corpus is fixed and re-synced.
- **A sic the corpus has marked (`[כך במקור]`) is taken as given.** The L4
  encodes the reading the corpus settled on; it is never re-litigated here
  and never filed as an L4 finding. The site does not show sic marks at all
  (the client, 2026-10-06): the text column is the corpus text, plain.
- `corpus/manifest.json` is the corpus's own document list and is the
  coverage page's denominator. A collection nobody has started is a row of
  nothing, not a missing row.

## What gets encoded: all the logic, not only pay

Every section of a document is encoded — eligibility, definitions,
procedures, obligations and prohibitions, cross-references — not just the
arithmetic. Obligations are regulative rules (`PARTY … MUST/MAY/SHANT …`
with `HENCE`/`LEST`), not booleans standing in for them.

- **Law-only reading.** A rule comes from the words of the section and the
  sections it cites. Never import a rate, a threshold or a reading from a
  payslip, a circular the section does not cite, or the Catala kernel. An
  amount the text says is set elsewhere ("הסכומים נקבעים על-ידי האוצר") is an
  INPUT (`GIVEN` / `ASSUME`), never a number made up.
- **Isomorphic.** One file per section, `l4/<corpus path>/<num>.l4`; inside
  it the clauses in the text's order, a `§§` per numbered paragraph.
- **Every paragraph is accounted for.** Each text row of the section is
  covered by a segment that cites it or an ancestor:
  - `@ref akn:<key>` on the declaration that encodes it, or
  - `-- akn:<key> <why this carries no rule>` — a source list, an amendment
    note, a pointer to a section encoded elsewhere. One line, in English like
    the rest of the site (the client, 2026-10-06: the site may be in English).
  `<key>` is a row key from `tools/akn.py`: an eId, or `<eId>/p<N>` for the
  N-th paragraph an element holds without an eId of its own. The tests fail
  on a key that is not in the section and on a text row nobody cites.
- **A cross-reference is an IMPORT or a named input, never a copy.** "כמפורט
  בפרק X" is a call into X's file when X is encoded, and a named `ASSUME`
  with the target in its `@desc` until it is.
- **Never resolve an ambiguity silently.** Where the text gives two answers,
  or none, the L4 says which reading it takes in a comment beside the rule,
  and the finding is filed (next section).

## Findings: errors the encoding exposes in the text

`findings/<corpus path>/<section>.toml` (one per section) is the register the site's "ממצאי L4" page and
`findings.json` show. Its model is MMS-415's (Linear), taken from L4 alone —
not from the Catala proofs, the corpus's ambiguity ledger or its sic kinds:

- `kind` — what is wrong with the LAW: `gap`, `overlap`, `contradiction`,
  `undefined-term`, `broken-reference`, `ambiguity`.
- `stage` — what CAUGHT it: `writing` (the text cannot be written as it
  stands), `compiling`, `examples` (the rules contradict a worked example or
  table the text itself states), `verification`. The tool's message is the
  evidence, not the category.
- `keys` — the rows it is about; `title` — one line; `body`; `quote` — the
  Hebrew words at issue, verbatim from the corpus;
  `reading` — the reading the encoding adopts to get past it;
  `depends_on` — earlier findings whose readings this one assumes;
  `read_by` and `review` (`unreviewed` until the lawyer has seen it): a
  finding is a legal reading and says whose.
- `l4` + `evidence` — a boolean in the section's file that is TRUE while
  the defect is in the text, asserted there with `#ASSERT`. It passes while
  the text is wrong; if the text is ever corrected the build goes red and
  the finding is stale, which is the point.

Three rules (MMS-415): nothing is fixed quietly to make the code compile —
every choice the text does not make is a finding with its reading; a later
finding names the readings it depends on; and the page shows the LAW's
flaws, one row per flaw, never our own L4 mistakes (those are bugs, fixed in
the L4). A corpus sic is not a finding.

The build also publishes `index.json` — a row per L4 segment with its file,
lines, names and corpus addresses `<akn path without .xml>#<eId>` — for the
corpus reader (MMS-414).

## Checks — run before every push

```
make l4        # tools/l4run.py: l4 run + l4 render on every file (needs `l4`)
make site      # tools/build_site.py → build/site/
make test      # python3 -m unittest discover -s tests
```

`l4 run` must report ok for every file: no type errors and every `#ASSERT`
true. Look at the rendered pages (desktop and phone width) for any change
that alters what a page looks like — a passing test is not a look.

The compiler is built from source at the revision in `toolchain/L4_COMMIT`
(`toolchain/build-l4.sh`); no Linux binary is published. Bumping the pin is
a deliberate change: rebuild, re-run everything, read the diff of
`build/l4/`.

## Documentation discipline

The same-commit rule from the corpus repo applies: a change to an encoding
that changes a finding, a coverage count or a page updates every place that
states the old fact in the same commit. Do not write counts into prose; the
coverage page computes them.

## Pacing (the client, 2026-10-07)

The usage limit is shared by everything a session runs. Twelve encoders
launched at once spent it within minutes, twice, and the work then stopped
for hours. Run at most TWO encoding agents at a time, start the next batch
only when one finishes, and prefer one well-checked batch over a wide
fan-out. Background loops (publish watchers) cost little; parallel agents
are what drain the limit.

