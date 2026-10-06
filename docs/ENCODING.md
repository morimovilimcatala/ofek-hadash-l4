# Encoding a section — the working method

The rules are in [CLAUDE.md](../CLAUDE.md); this is how to apply them to
one section. The worked example is §1.7:
[`l4/takanon/takanon-sherut-ovdei-horaa/1.7.l4`](../l4/takanon/takanon-sherut-ovdei-horaa/1.7.l4)
and its findings,
[`findings/takanon/takanon-sherut-ovdei-horaa/1.7.toml`](../findings/takanon/takanon-sherut-ovdei-horaa/1.7.toml).
Read both before writing a line. The L4 language reference is the
`writing-l4-rules` skill (legalese/l4-ide `skills/writing-l4-rules/`) and
https://legalese.com/l4/.

## The loop

1. `python3 tools/rows.py <num>` — the section's rows and the key each is
   cited by. Read the whole section first, in Hebrew, and the sections it
   cites.
2. Write `l4/takanon/takanon-sherut-ovdei-horaa/<num>.l4`.
3. `python3 tools/check.py <file>` until it prints `ok: True`. Every
   `#ASSERT` must hold. (`l4 check` exits 0 even with errors — the gate is
   `ok`.)
4. `python3 tools/rows.py <num> --todo` prints nothing: every paragraph is
   cited.
5. Findings, if any, in `findings/takanon/takanon-sherut-ovdei-horaa/<num>.toml`.

## What a file looks like

```l4
-- תקנון שירות עובדי הוראה, פרק <chapter>, §<num> <heading>
-- One or two lines: what the section governs.

IMPORT prelude
IMPORT common

§ `<num> <heading>`

§§ `<num>.<para>`

@ref akn:<key>
GIVEN …
GIVETH …
DECIDE `a name that reads like the rule` … IS/IF …

-- akn:<key> One line: why this paragraph carries no rule.
```

- **Everything is encoded, not only pay.** Eligibility and conditions are
  `DECIDE … IF`; amounts are `DECIDE … IS`; definitions are `DECLARE`
  records/enums; duties, permissions and prohibitions are regulative rules
  (`GIVETH A DEONTIC Party <action type>`, `PARTY … MUST/MAY/SHANT … WITHIN
  … HENCE … LEST BREACH BY … BECAUSE "…"`), each exercised by at least one
  `#TRACE` where it has a deadline.
- **A note is for a paragraph with no rule in it**: an אסמכתא list, "סעיף זה
  תוקן ב…", a heading-only row, a pure pointer ("ראה סעיף 3.9.4") to a rule
  encoded in another section. A paragraph that SAYS something — even
  something vague — gets a rule, and the vagueness is a finding.
- **Inputs, never invented numbers.** An amount the text leaves to someone
  else is a field or `GIVEN` with an `@desc` saying who sets it. Examples
  use round placeholder figures and say so.
- **Cross-references** to another section are a named input (`GIVEN` /
  `ASSUME` with an `@desc` naming the section) — sections do not import
  each other yet.
- **English identifiers and notes**; Hebrew only inside `§` titles,
  comments quoting the text, and finding quotes.

## Findings

A finding is a flaw in the LAW (CLAUDE.md, "Findings"). The evidence is a
boolean that is TRUE while the flaw is in the text, `#ASSERT`ed in the
section's file, named exactly in the finding's `evidence`. Ids are
`F-<num>-<letter>`. Every finding has `kind`, `stage`, `keys`, `quote`,
`title`, `body`, `reading`, `l4`, `evidence`, `read_by = "Claude (L4
encoder)"`, `review = "unreviewed"`. Copy the shape from 1.7.toml.

What counts: a table with overlapping or missing rows; two clauses giving
different answers to one case; a case the text does not decide; a term
used and never defined; a reference to a clause, annex or chapter that is
not there; wording that reads two ways where the readings give different
results. Not a finding: our own L4 mistake, a corpus sic, a typo the
reader can see past, a dated amount.

## L4 traps already hit here

- `ok` from `l4 run` ignores a FALSE `#ASSERT`; `tools/check.py` and
  `tools/l4run.py` gate on both.
- `NOT` binds loosest: `NOT a AND b` is `NOT (a AND b)`, and `(NOT a OR b)`
  is `NOT (a OR b)` — not the implication it reads as. Write `(NOT a)`.
  `tools/layout_lint.py` (and the suite) flags a NOT followed on its own
  line by AND/OR at the same bracket depth, whichever was meant.
- `a DIVIDED BY b TIMES c` is `a / (b × c)`. Parenthesise.
- A mixfix call (``d `is on or after` e``) binds looser than `OR`.
- No record update (`x WITH f IS v`); a multi-line `WITH` inside `#ASSERT`
  does not parse — name the record first.
- **A line that begins with an operator takes the rest of THAT LINE as its
  right operand.** `10 MINUS 3 MINUS 2` ⏎ `MINUS 1 MINUS 1` is 5, not 3. Put
  one operand on each continuation line (`a` ⏎ `PLUS b` ⏎ `PLUS c`), or
  bracket. `tools/layout_lint.py` (and the suite) refuses the regrouping
  kinds; a PLUS/TIMES chain is flagged too, because `l4 render` shows the
  regrouped rest as one item.
- `IMPORT prelude` explicitly — `map`, `filter`, `sum`, `min`, `all`,
  `count` come from it.
- Record field names are global within a file and across `IMPORT`: two
  records with a field `days` make every `x's days` ambiguous. Give fields
  specific names (`length in days`, `band days`).
- `§` inside an annotation's text (`@desc`, `@export`) starts a section and
  breaks the parse. Write "section 1.7", not "§1.7", in annotations.
- In `MUST`/`MAY`/`SHANT`, the action is a PATTERN, not an expression:
  `MUST pay (f x)` fails. Bind and guard:
  `MUST \`pay\` amount PROVIDED amount AT LEAST f x`.
- `@ref` takes the rest of its line: `@ref akn:<key>`, no quotes. Several
  keys on one line are allowed: `@ref akn:<key1> akn:<key2>`.
- A `§§` heading may sit above a blank line before its rule; it is shown
  with the rule below it.
- `common.l4` holds `Party`. Do not edit it; if a section needs an actor it
  lacks, declare a section-local party type (`DECLARE \`1.28 party\` IS ONE
  OF …`) and say so in the hand-off.

## Circulars (and any document that is not divided into sections)

A circular is ONE unit: `l4/<collection>/<file>.l4` beside the corpus's
`akn/<collection>/<file>.xml`, findings in `findings/<collection>/<file>.toml`
(`l4 = "l4/<collection>/<file>.l4"` in each finding). `common.l4` in each
collection directory is a link to the takanon's, so `IMPORT common` works.

    python3 tools/rows.py circulars/2016-17_tashaz_05          # its rows and keys
    python3 tools/rows.py circulars/2016-17_tashaz_05 --todo

- **Front matter and sign-off** are keyed `preamble/…` and `conclusions/…`.
  The letterhead, date, reference number, addressee and greeting carry no
  rule: one note on `akn:preamble` covers them all (an ancestor key covers
  its rows). The sign-off's contact line, signature and copies likewise
  (`akn:conclusions`) — unless a line in it SAYS something (a deadline, an
  instruction to the owners), which then gets a rule of its own.
- **A table is one row**, keyed `<holder eId>/t<N>` and shown as a table.
  Encode it as data (a LIST of records, one per printed row, in the
  printed order) and cite the table key on that declaration. Overlapping or
  missing rows are findings, as in §1.7.
- **A circular carries AMOUNTS and DATES** where the takanon leaves them to
  "the circulars". Here they are data, with the date they take effect as
  printed. A circular never outranks an agreement: where it restates an
  agreement's rule, encode what the circular says and cite the agreement it
  names in a comment; where the two disagree on the page, that is a
  finding (kind `contradiction`), not a correction.
- **Instructions to the owners (הבעלויות) are regulative rules**: PARTY
  `the employer` (or the owning body) MUST pay / report / deduct … WITHIN
  the month the circular names, with a `#TRACE`.
- Each circular is encoded on its own words. Do not import another circular;
  name what it relies on as an input with an `@desc` saying where it comes from.
