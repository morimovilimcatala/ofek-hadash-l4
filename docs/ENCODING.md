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
- `NOT` binds loosest: `NOT a AND b` is `NOT (a AND b)`. Write `(NOT a)`.
- `a DIVIDED BY b TIMES c` is `a / (b × c)`. Parenthesise.
- A mixfix call (``d `is on or after` e``) binds looser than `OR`.
- No record update (`x WITH f IS v`); a multi-line `WITH` inside `#ASSERT`
  does not parse — name the record first.
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
