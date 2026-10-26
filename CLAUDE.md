# Working rules for this repo

This repository encodes the Ofek Hadash corpus in L4 and publishes a site
that sets each section's TEXT beside its L4. The text is the corpus's; the
reading of it is ours. Use the L4 skill (`writing-l4-rules`, from
legalese/l4-ide `skills/`) for anything about the language.

## Work is tracked in Linear, project `L4 encoding`

The L4's own work — an encoding batch, a property-check pass, a site or
findings change — is an issue in Linear team `MMS`, project `L4 encoding`
(the client, 2026-10-12: from 2026-10-07 to 2026-10-12 none was filed,
MMS-454 records them after the fact). A defect in the corpus text still goes
to `AKN corpus`, as above. The corpus repo's live-status rule applies here
unchanged: In Progress the moment work starts, a comment per shipped commit,
Done in the same step as the push that finishes it, back to Backlog with a
reason when work stops, and nothing open written in a markdown file.

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
  until the corpus is fixed and re-synced. An issue whose answer turns on
  what a page prints carries the page (the client, 2026-10-11, MMS-440):
  crops of the source's own pixels, enlarged by nearest-neighbour only and
  never retouched, titled with file, page, resolution and pixel box, plus
  a wider context image, shown inline in a comment — the corpus repo's
  CLAUDE.md states the rule in full.
- **A sic the corpus has marked (`[כך במקור]`) is taken as given.** The L4
  encodes the reading the corpus settled on; it is never re-litigated here
  and never filed as an L4 finding. The site does not show sic marks at all
  (the client, 2026-10-06): the text column is the corpus text, plain.
- **One exception: statutes (the client, 2026-10-20, MMS-516: "don't
  encode it in AKN, only in L4").** The corpus holds no copy of a law (its
  standing decision 14), and two are encoded here anyway — חוק הסכמים
  קיבוציים §§2, 15, 16, 19–23 (MMS-600 pinned §§2, 15 and 16) and חוק יסודות
  התקציב §§21, 29, 32 (MMS-528): their
  sections' words are pinned in `laws/<name>.toml` with the live ספר החוקים
  הפתוח page they are read from and the date they were last checked against
  it, and its rules are `l4/laws/<name>.l4`, a `§§` block per section citing
  `@ref law:<num>`. A file that applies it imports it through a link in its
  own directory named `<name with underscores>.l4`, as with `conventions.l4`.
  The site shows it at `laws/<name>.html`, text beside rules.
- `corpus/manifest.json` is the corpus's own document list and is the
  coverage page's denominator. A collection nobody has started is a row of
  nothing, not a missing row.
  It also carries the corpus's own coverage verdict per document (`state`,
  `row`), computed at sync by the corpus's code (`tools/sync_corpus.py`):
  the coverage page draws a document the corpus holds only in part yellow
  from that verdict, never from a reading of the provenance notes of our
  own (the client, 2026-10-22: "isn't the corpus the source of truth?").

## What gets encoded: all the logic, not only pay

Every section of a document is encoded — eligibility, definitions,
procedures, obligations and prohibitions, cross-references — not just the
arithmetic. Obligations are regulative rules (`PARTY … MUST/MAY/SHANT …`
with `HENCE`/`LEST`), not booleans standing in for them.

- **Law-only reading.** A rule comes from the words of the section and the
  sections it cites. Never import a rate, a threshold or a reading from a
  payslip, a circular the section does not cite, or the Catala kernel. An
  amount the text says is set elsewhere ("הסכומים נקבעים על-ידי האוצר") is an
  INPUT, never a number made up: a section `GIVEN`, indented under the `§`
  heading of the section whose rules read it, its `@ref` on the line above.
  `ASSUME` is retired (l4-ide `unstable` warns on it, and a warning fails the
  build); the 70 there were moved on 2026-10-22.
- **Say why there is no answer (MMS-538).** Where a provision gives no
  answer, the file states which kind of gap it is, once, as data, with
  `why there is no answer` (`l4/lib/vocabulary.l4`): `the text is missing`
  (a page the scan lacks, a document held without its words),
  `outside the corpus`, `not yet encoded`, `set elsewhere` (delegated, no
  flaw), or `the text is silent` (a lacuna, naming its gap finding). A
  lacuna is declared only where the whole provision and all it cites are
  held. A document the corpus holds in part states what it lacks
  (`tests.test_missing`); the של"ח is the first.
- **Isomorphic.** One file per section, `l4/<corpus path>/<num>.l4`; inside
  it the clauses in the text's order, a `§§` per numbered paragraph.
- **One codebase, one namespace (the client, 2026-10-21, MMS-524: "don't
  patch the compiler … go with unique names").** Every module's file name is
  unique in the repository, because the pinned compiler finds an import by
  its bare name. A sectioned document whose numbers would collide carries a
  prefix (`akn.MODULE_PREFIX`): the base agreement's §70 is
  `base-agreement-70.l4`, the takanon's §1.1 stays `1.1.l4`. `l4/modules/`
  links every module under its one name and is on every run's
  `JL4_LIBRARY_PATH` (`tools/modules.py --write` after adding a file;
  `tests.test_repo.OneNamespace` holds it), so ANY file imports ANY module
  by name: `` IMPORT `base-agreement-70` `` from a circular works. A file
  imported through a link resolves its own imports from the link's
  directory, which is why the links all live in one directory.
  A TYPE NAME IS DECLARED ONCE, too: two modules declaring one name cannot
  be imported into the same file ("multiple definitions for the
  identifier"). `Party` lives in `l4/lib/parties.l4` (MMS-532) and a new
  party is added there; a dotted takanon section is imported as
  `takanon-<dashed>` (`takanon-1-29`). The names still declared twice — the
  yearly circulars' — are an exact ratchet in `tests.test_repo.OneNamespace`.
  A CONSTRUCTOR NAME (a case of `IS ONE OF`) is shared the same way
  (MMS-603): two with one name fail wherever the use does not fix the type
  (`PARTY \`x\``). The modules every collection reaches, `l4/lib/` and
  `l4/laws/`, declare none another module declares, and the rest's count is
  an exact ratchet in the same test.
- **Every paragraph is accounted for.** Each text row of the section is
  covered by a segment that cites it or an ancestor:
  - `@ref akn:<key>` on the declaration that encodes it, or
  - `-- akn:<key> <why this carries no rule>` — a source list, an amendment
    note, a pointer to a section encoded elsewhere. One line, in English:
    a note is part of the L4 source, as the identifiers are. The site
    itself is in Hebrew (the client, 2026-10-10: "besides for the
    L4-to-English, the website should be in Hebrew"), and so are the
    findings (2026-10-11: a finding shown in English "should be Hebrew").
  `<key>` is a row key from `tools/akn.py`: an eId, or `<eId>/p<N>` for the
  N-th paragraph an element holds without an eId of its own. The tests fail
  on a key that is not in the section and on a text row nobody cites.
- **A cross-reference is an IMPORT or a named input, never a copy.** "כמפורט
  בפרק X" is a call into X's file when X is encoded, and a named input (a
  section `GIVEN`) with the target in its `@desc` until it is. This holds ACROSS documents
  (MMS-521): a circular that applies an agreement's rule imports the
  agreement's module rather than re-encoding the rule; an amendment encodes
  what it changes, dated, and imports the rest.
- **Never resolve an ambiguity silently.** Where the text gives two answers,
  or none, the L4 says which reading it takes in a comment beside the rule,
  and the finding is filed (next section).

## The root: one entry point, precedence once (MMS-521)

The client, 2026-10-21: "one source of truth to query the law which 'uses'
all the files to give one answer", and disagreements raised as errors.
- **A shared vocabulary**, `l4/lib/vocabulary.l4`: the `pay item`s two or
  more instruments speak about, one `teaching case` record of the facts they
  ask, and the `instrument` record. An instrument's file imports it,
  describes itself (`instrument`: kind, date, §29 facts) and adds `<item>
  according to <instrument>`, a `MAYBE` answer from its own rules (NOTHING
  where it does not speak). Nothing in the roots names an item but data.
- **Every root is an interface** (the client, 2026-10-22: "each root should
  be an interface, agreement precedence is the agreement root's
  responsibility"): a `collection root` record (`l4/lib/precedence.l4`) —
  the instruments it includes, `what each says` for an item and a case, and
  `its ruling`, by the collection's own rule. `l4/lib/takanon-root.l4` (one
  provision speaks), `agreements-root.l4` (§23, the provision in the
  employee's favour) and `circulars-root.l4` (the later circular over the
  earlier, `precedence.later-circular`). The agreements' root holds one root
  per family of agreements, as the corpus groups them (MMS-548):
  `ofek-hadash-root.l4`, `oz-latmura-root.l4` (each family rules among its
  own agreements by §23, the agreements' root among the families), each with
  its page in its family (agreements/ofek-hadash/root.html). A collection's
  tests hold its own ruling.
- **Precedence between collections, once**, `l4/lib/precedence.l4`: the
  takanon's introduction, then §29 and §22 between an agreement and the
  employer's term. The root folds over the list of collection roots and
  settles their rulings by these alone. No instrument keeps its own copy.
- **Tests sit beside what they test, not in it** (the client, 2026-10-22:
  "assertions about a file should sit next to it, not be included in it").
  A root's every `#EVAL` and `#ASSERT` is in `l4/tests/<root>-tests.l4`,
  which imports it; `make l4` checks the root through that file (so it is
  loaded once), and the root's page shows the tests below its code.
- **The root**, `l4/lib/root.l4`: the one public answer, `the answer that
  governs` item case, for any case, and whether a case's claims disagree
  (`the contradictions on` item case). It holds no question (the client,
  2026-10-22: "the root shouldn't be asking questions at all, they should
  be in the test file"). Its tests, `l4/tests/root-tests.l4`, hold what was
  checked: each item's grid of cases (`the cases checked for` item), the
  contradictions found over it, `the resolutions` — each naming the
  instrument that governs and the rule, which precedence must agree with —
  and the gate, `unresolved contradictions`, `#ASSERT null`. The
  disagreements stay asserted there as evidence.
- **The month by the law**, `l4/lib/salary-root.l4` (MMS-525; the client,
  2026-10-22: "if a teacher wants to know his salary he wants to know the
  law, he doesn't care about the underlying documents"): what the
  calculator asks. §1.1's components, each `the component that governs` —
  the root's answer where a pay item stands for the component (`the pay
  item of`), §1.1's own figure, marked as such on the page, where none does
  yet — and why: the instrument that governs, the rule, what each one says.
  A new pay item for a §1.1 component is one line in `the pay item of`. Its
  tests, `l4/tests/salary-root-tests.l4`, hold §1.1's worked example and a
  case the agreement of 24.1.2008 governs. The page ships it and every
  module it reaches without their `#EVAL`/`#ASSERT` lines
  (`calculator.without_tests`): loading the law then takes the browser
  half a minute to two minutes, and an answer after it about a second.
- The site shows each root on its own page (`tools/roots.py`: root.html,
  circulars/root.html, …), read off the module and `make l4`'s results.
  A root imports whole families of instruments, the heaviest check there
  is; `make l4` checks it and does not render it (`tools/l4run.py`
  `is_a_root`). A check's memory grows with the source it imports (under
  1.5 GB per MB at l4-ide unstable; the root ~1.5 GB, about a minute):
  `make l4` reserves each check's estimate out of the machine's memory.
  (At the old pin the root took ~21 GB and 25 minutes, and was checked on
  demand only; MMS-551.)
- Traces and the calculator run tools/assets/l4wasm/l4.wasm, built from
  l4-ide `unstable` at `toolchain/L4_WASM_COMMIT` (MMS-535). It loads a module
  two importers share, so it loads the root, and a second call on the same
  imports reuses the first call's type-checked modules: a page pays for
  checking the root once, not per click. Each call still evaluates the
  imports afresh, so a trace through them is the same on every call.

## Findings: errors the encoding exposes in the text

`findings/<corpus path>/<section>.toml` (one per section) is the register the site's "ממצאי L4" page and
`findings.json` show. Its model is MMS-415's (Linear), taken from L4 alone —
not from the Catala proofs, the corpus's ambiguity ledger or its sic kinds:

- `kind` — what is wrong with the LAW: `gap`, `overlap`, `contradiction`,
  `undefined-term`, `broken-reference`, `ambiguity`, `edge-case`.
  A `contradiction` IS BETWEEN SOURCES OF EQUAL POWER (the client,
  2026-10-22: "a weaker one departing from a stronger one has its own page,
  סתירה in finding means equal power"): a document against itself, or two of
  the same rank (two circulars). A weaker source departing from a stronger
  one — a circular from the agreement or the letter it carries out, an
  answer on the site from the takanon, the takanon from a circular or an
  agreement — is a card on מקורות סותרים (`data/contradictions.json`, the
  groups in `contradictions.CROSS_RANK`). The finding that records it stays in
  the register, its `#ASSERT` the card's evidence, and is shown on its card
  only: the findings page, its counts and the rows' flags leave it out
  (`contradictions.homes`).
  AN EDGE CASE IS A FINDING ONLY WHEN IT EXPOSES A FLAW (the client,
  2026-10-21, MMS-534: "only interesting מקרי קצה should appear in findings,
  otherwise it isn't a finding"): stretched to an input the text did not
  picture, the rules give a result it plainly did not intend (no cap where
  one is expected, an absurd amount) or a result two instruments dispute.
  An edge case the text answers on purpose — an explicit cap, a stated
  limit — is an `#ASSERT` in the section's file and not a finding, and so is
  one no outcome turns on: an `edge-case` graded `low` is refused. One flaw
  is one row: a further input showing the same flaw goes into that row's
  body and `trace`, not a row of its own. An edge case carries `trace`, the
  L4 expressions the site runs to show how the rules compute it.
- `stage` — what CAUGHT it: `writing` (the text cannot be written as it
  stands), `compiling`, `examples` (the rules contradict a worked example or
  table the text itself states), `verification`. The tool's message is the
  evidence, not the category.
- `severity` — the flaw's REAL-WORLD impact (the client, 2026-10-20,
  MMS-506: "if a mistake won't tickle a court then it isn't severe";
  "high = court will most likely rule to change the status quo"). The status
  quo is how the ministry applies the text, as its own documents in the
  corpus record it — circulars, joining circulars, later instruments; never
  a payslip. `high`: money, eligibility or a right turns on it and a court
  would most likely rule against the status quo (typically a circular
  applying a reading the governing agreement does not support); `medium`:
  money or a right is touched but the status quo would most likely stand, or
  it is a toss-up, or it touches a procedure; `low`: no outcome turns on it.
  `severity_why` names the status quo and says why, in one Hebrew line. The
  findings page shows them as a meter and a filter.
  PAYSLIPS ARE EVIDENCE OF THE STATUS QUO FOR THE GRADE ONLY (the client,
  2026-10-20: "allow payslips for severity grading"; the corpus repo's
  decision 17). They never change an encoding or a reading — the law-only
  rule above stands for those — and a `severity_why` that rests on them says
  what is paid in general terms, never a name, an identity number, a
  person's amount or month.
- `title`, `body` and `reading` are written in HEBREW; an L4 identifier
  inside them stays in backticks, in English, and the site isolates it.
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

**Every ambiguity's reading follows a convention** (the client, 2026-10-14,
MMS-485: "all ambiguities decisions should follow a convention"). The
conventions are `conventions.toml`, published as the site's "מוסכמות" page: one
row per choice the text leaves to the encoding (how a figure is rounded when
the text names no rounding, whether a period's last day is in it, which of
two provisions prevails), each naming the L4 rules that apply it. A finding
of kind `ambiguity` names the one its reading applies in `convention`; a
reading decided case by case is refused by the tests. A new kind of question
gets a new convention, written generally enough to decide the next case, and
a reading that departs from one is either brought into line or recorded as
that convention's exception with its reason.

**A question waiting on the lawyer gets a pick here** (the client,
2026-10-17; the corpus repo's standing decision 16). A legal reading put to
Zvika — a misquoted amendment, two same-day wordings, a misprinted year — is
not left open: the pick is a convention carrying `lawyer = "<the issue that
asks him>"` and the corpus places that apply it (`corpus`). The page lists
every such pick under "לעיון עורך הדין"; he reviews them there and may revert
any of them.

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
make roots     # only the roots and their tests
```

`make l4` and the deploy check the roots and their tests with every other
file (since the pin moved to l4-ide unstable, 2026-10-22; they were checked
on demand while a root cost ~21 GB and 25 minutes). `L4_ROOTS=skip make l4`
leaves them out of one local run; nothing that skips them holds the gate.

`l4 run` must report ok for every file: no type errors, every `#ASSERT`
true, and no compiler warning about the file — a warning is refused like an
error, because the one the tree carried ("AND and OR operators appear at the
same indentation level") is a grouping the reader cannot see.
`tools/layout_lint.py` (run by the suite) refuses three more shapes the
compiler accepts silently: a continuation line that regroups arithmetic, a
NOT that runs on into AND/OR, and a bare `N%` as a function's argument,
which the pinned compiler reads as `(the call)%` (MMS-510) — write `(N%)`. Look at the rendered pages (desktop and phone width) for any change
that alters what a page looks like — a passing test is not a look.

The compiler is l4-ide at the revision in `toolchain/L4_COMMIT`, installed by
`toolchain/fetch-l4.sh` from legalese/prereleases (MMS-558), Legalese's shelf
of standalone builds from `unstable` (the client, 2026-10-24: "a recent
unstable binary which will run much cooler"). `toolchain/L4_SHELF` names the
release and pins each archive's sha256; the script refuses a release that is
not a build of the pin, an archive whose hash differs, or a platform the
shelf does not build (linux-x64 and darwin-arm64 are), and never falls back
to another build. The darwin-arm64 build is a native arm64 binary linking
only system libraries (the shelf smoke-tests it on macOS), which replaces
running the Linux `l4` in Docker under x86 emulation. Bumping the pin is a deliberate change: the shelf needs
a release at the new commit (cut by Legalese, `prerelease.yml`), then new
lines in `L4_SHELF`; rebuild the wasm, re-run everything, read the diff of
`build/l4/`. `toolchain/build-l4.sh` builds a commit from source for an
experiment the shelf has no release for (`measure-compiler.yml`). Both pins
are l4-ide `unstable` (the client, 2026-10-22: "we should always use
unstable"): `L4_COMMIT` joined `L4_WASM_COMMIT` at c9a3fe3, and the two are
kept equal. c9a3fe3 is the commit MMS-551 measured (the root in ~40 s and
~1 GB, against ~25 min and ~27 GB at the old pin). The shelf ships no wasm:
`toolchain/build-wasm.sh` builds it, in an arm64 Linux container on a Mac.

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

