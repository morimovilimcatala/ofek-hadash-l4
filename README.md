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
25.12.2008 and the Oz LaTmura agreement of 14.8.2011 are read part by part
and article by article, with the preamble, the sign-off and each annex a
section of its own (`tools/akn.py`'s `SECTIONED`).
An agreement the corpus publishes without its text (an OCR layer it
refused) has nothing to encode until the corpus reads its pages.

The salary tables are in work too (MMS-610): every table the corpus's
`tables/` collection publishes — the tables the agreements annex, and the
tables of the conditions-of-service portal — is data, cell for cell, in the
collection's types (`l4/tables/tables-common.l4`), and each file checks its
table against what produces it: the agreement whose annex it is, the round
that updated it, the steps it prints.

## Layout

| Path | What |
|---|---|
| `corpus/` | read-only snapshot of the corpus's Akoma Ntoso (`SOURCE.toml` names the commit) and its document list |
| `l4/<corpus path>/<section>.l4` | one L4 file per section, laid out like the corpus; every module's file name is unique (the base agreement's sections are `base-agreement-<N>.l4`, the Oz LaTmura agreement's `oz-founding-<N>.l4`) |
| `l4/modules/` | a link to every module under its one name, on every run's `JL4_LIBRARY_PATH`, so any file can import any module (`tools/modules.py`, MMS-524) |
| `conventions.toml`, `l4/conventions.l4` | the rules of reading the encoding follows where the text does not decide, and the one L4 definition of each that is a computation, which the rules import |
| `findings/<corpus path>/<section>.toml` (one per section) | errors in the text the encoding exposed, each backed by an `#ASSERT` |
| `data/calculator-delta.json` | the comparison with the ministry's salary simulator: inputs, outputs, mappings, clauses and classifications only (written outside this repository; shown as the simulator's group of the contradictions page) |
| `laws/<name>.toml`, `l4/laws/<name>.l4` | a statute encoded though the corpus holds no copy of it (חוק הסכמים קיבוציים §§2, 8, 9, 13, 15–16, 19–23, 25; חוק שירות המדינה (גמלאות) §§1, 8, 10, 17א, 22, 35, 63א; חוק הביטוח הלאומי §§22, 50; חוק יסודות התקציב §§21, 29, 32; חוק שכר מינימום §§1–3, 11; חוק הגנת השכר §§1, 9, 19א, 20, 25; חוק פיצויי פיטורים §§1–9, 11, 11א, 12, 13, 13ב, 14, 15, 16, 29–31; חוק עבודת נשים §§6, 6א, 7, 7א, 8, 9, 10, 19, 23; חוק שוויון ההזדמנויות בעבודה §§2, 3, 4, 17; חוק דמי מחלה §§1, 2, 4, 4א, 5, 6, 12, and its laws of absence for a child's illness §§1, 1א, 1ב, 1ג, 3, 3א, a parent's §§1, 3, 4, 4א, a spouse's §§1, 1א, 3, 4, 5 and a partner's pregnancy §§1, 3, 4; חוק חופשה שנתית §§1–8, 10, 13, 15, 33, 38; חוק שעות עבודה ומנוחה §§1, 2, 3, 5, 6, 7, 9, 16, 17, 18, 20, 30, 31, 35; חוק שכר שווה לעובדת ולעובד §§1, 2, 3, 6, 12, 13, 14; חוק הודעה מוקדמת לפיטורים ולהתפטרות §§1–7, 10, 11, 12; and the others `laws/` holds): its sections' words pinned from ספר החוקים הפתוח, and their rules |
| `data/statute-citations.json` | every statute the corpus cites and every section it cites by number, with the documents that cite it, read off the corpus's own links to ספר החוקים הפתוח (`tools/statute_citations.py`, MMS-601) |
| `tools/statute_record.py`, `data/statute-set-aside.toml` | the per-instrument record of the protective statutes (MMS-601): every document of the manifest against every statute the statutes' root registers — it meets the floor (an `#ASSERT` in its L4 that reads the statute, and holds), falls short of it (a card or a finding), was not weighed (the reason a `-- not weighed against` comment in its file gives, a row of `data/statute-set-aside.toml` for a document with no L4, or none of the terms the statute's batch searched for, `inventory` in `laws/<name>.toml`, is in its text), or was not checked; read off the source, never written by hand |
| `data/contradictions.json`, `data/contradictions/` | the hand-written layer of the contradictions page, whose rows the root generates where it can speak (MMS-521): a card attaches to the root's row by key (`root`) and brings a side per source with its answer — a document with a crop of its page, or what the payslips or the simulator pay — and the rule's prose; a card the root cannot speak for says why (`not_in_root`); a circular against an agreement says which way it departs, and where it gives more, what §29 of the Budget Foundations Law makes of the excess |
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
  agreements), the tables by folder (the agreements' annexes, the portal's
  tables), the circulars by school year. Each section
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
  agreement, and §§2, 15–16, the two kinds of agreement (special and
  general) and whom each applies to, encoded in L4 and set beside their text
  (MMS-516, MMS-600). The law ranks neither kind above the other: two
  agreements that both apply meet in §23. The corpus
  keeps no copy of the law; the text is pinned in `laws/` from the live page.
  A circular whose rule pays less than the agreement it implements applies
  §22 through it (`l4/circulars/2008-09_tashsat_03.l4`).
  §§8, 9, 13 and 25, which the corpus cites — accession, the stamp-duty
  exemption, the term of an agreement for a fixed period and the extension
  order — were pinned in the statute pass (MMS-601): the Shelah agreement of
  1978 and the takanon's §6.20 make owners party by §8(2)'s letter, and Oz
  LaTmura's §63 asks for an extension order §25 gives only for a general
  agreement.
- **The State Service (Pensions) Law** (`laws/state-service-pensions-law.html`)
  — §§1, 8, 10, 17א, 22, 35 and 63א, every section the corpus cites
  (MMS-601): who is a State employee for it, the determining salary and the
  fixed supplement, how service is counted, the early pension, the grant on
  dismissal before 60, the pension of one back in the service, and the
  security services. Each wage agreement's statement that its supplement
  counts in the determining salary "in the light of section 8" passes
  through §8: a supplement the Government recognises is in it, and since
  1.6.2023 an agreement may leave a new component out, which the 2023
  framework does not do. The college-reform grant and its circulars set off
  the §22 grant the law computes; the takanon's §1.25.7 counts earlier
  service by §10(4) and its §1.23 names §35's pensioner. It is the budgetary
  pension itself, not a floor, and is not in the statutes' root.
- **The Budget Foundations Law** (`laws/budget-foundations-law.html`) —
  §29, which voids a wage term a budgeted or supported body (a local
  authority, a school owner) pays beyond what was agreed for all state
  employees unless the Finance Minister approved it, with the definitions
  of §§21 and 32 (MMS-528). A circular to the owners that pays more than its
  agreement passes through it before §22 (`l4/circulars/2009-10_tasha_02.l4`).
- **The Minimum Wage Law** (`laws/minimum-wage-law.html`) — §§1–3 and 11:
  the minimum wage (an input, published by notice), who is owed it in
  proportion to his position and the time he worked, which components of
  pay count toward it, and that the law adds to an agreement and never takes
  from it (MMS-601). An agreement that leaves its supplement out of the pay
  that counts gives more than the law
  (`l4/agreements/ofek-hadash/2016-09-30_ofek-hadash_september-2016-agreement.l4`).
- **The Wage Protection Law** (`laws/wage-protection-law.html`) — §§1 and
  9, the day a month's wage is due; §19א, a provident-fund contribution not
  paid within 21 days of it counts as wages withheld; §20, the compensation
  for severance paid late; and §25, what may be deducted from wages and how
  much (MMS-601). The provident-fund agreements of 17.12.1998 contribute
  with the month's wage, within §19א. The takanon's §1.28.2.3 restates §20 with 60
  days where the law gives the employer 15 to notify the fund; the law
  governs, a card on the contradictions page. An overpayment an agreement
  deems an advance under §25(א)(7) is deducted in twelve parts only as §25
  allows (`l4/agreements/ofek-hadash/2012-02-29_ofek-hadash_amendment_hascam-hashlama.l4`).
- **The Severance Pay Law** (`laws/severance-pay-law.html`) — §§1–9, 11,
  11א, 12, 13, 13ב, 14, 15, 16, 29, 30 and 31: who is owed severance — after
  a year of continuous work, through the breaks §2 lists, on a dismissal,
  the employer's end or the employee's death, and on the resignations the
  law counts as dismissals — a month's wage a year, the wage the
  regulations set and its minimum-wage floor, how far a payment to a fund
  or a pension takes its place — as far as the collective agreement says —
  when the agreement may deny it, and that a release needs writing
  (MMS-601).
  The 1999 pension-transition agreement's 28% completion is exactly what
  §14 leaves after its 72%, and the Oz LaTmura agreement's §46(ה) leaves none.
  The takanon's §1.28.2 restates the law without naming it, and gives what
  it gives: the year of work and the change of employers, the first-year
  presumption, the employer's end and the survivors, the resignations for
  health, on a fixed term's end and the others of §11 — its ages 60 and 65,
  §11(ה) before the Retirement Age Law, give more — the police recruit, the
  rate, the fund and the pension in place of severance, the agreement that
  denies it, the release and the State. Two places print an earlier text
  that gives less, each a card on the contradictions page where the law
  governs: a break that severs the relationship keeps the work continuous
  up to 3 months (item 2(ט)), where §2(9) says six; and the resignation to
  care for an adopted child reaches only a child under nine months, where
  §7 reaches one adopted before 13, within nine months of receiving him,
  and the surrogate and foster child the takanon does not name.
  Within the floor besides: the 8⅓% that takes the place of the whole of
  severance (circular תשע"ב/6), the 13⅓% and 18⅓% that take its place for
  an additional position (the Dafna summary of 1984, the takanon's §1.24),
  and the takanon's head of a local authority, whose resignation is a
  dismissal with no exception (§1.39). Most documents that name severance
  do so only to count a supplement in the wage it is computed on, or to
  leave a grant out of it — §13 sends that to the regulations, which
  compute the wage by the collective agreement — or as the base of the
  jubilee grant or of another payment; their files say they were not
  weighed, and why, and so does `data/statute-set-aside.toml` for the five
  that have no L4, the pension transfer of 30.12.2009 among them.
- **The Women's Work Law** (`laws/womens-work-law.html`) — §§6, 6א, 7, 7א,
  8, 9, 10, 19 and 23: the birth and parenthood period (26 weeks, 15 for one
  with fewer than twelve months) and its extensions, the absences the law
  allows (a miscarriage, pregnancy, the months after the period, the
  parent's hour, fertility treatment, check-ups, the extension of up to a
  year), the provident-fund contributions through the period, that no one is
  employed in it, the limits on dismissal, overtime and night work, and that
  every better right stands (MMS-601). The agreements and circulars that
  count "the birth and parenthood period as §6 means it" towards a grant,
  the base agreement's §25 and the employment circulars' nursing hour, and
  the 2023 framework's §70(ב) give at least what it guarantees. So do the
  documents that count the period or the leave as work or employment — for
  promotion, seniority, recuperation pay, a grant's months, the converted
  pay of the reform and its principals (the 2007 and 2008 Ofek agreements
  and its signed copy, the 2022 wage agreement, the Oz agreements of 2011,
  2018 and 2024, the colleges' 2019 amendment, the excellence and
  persistence circulars, the takanon's §§1.7 and 1.29, the wages
  commissioner's 2023-1-12) — that leave the period out of a furlough or
  an arrangement (the 2020 framework agreements), that ask no work in it
  (§8; circular תש"פ/7), and that give §25's hour to principals, first
  deputies and של"ח teachers. Where a document names the leave only as an
  occasion for a substitute, or sets a grant for hours taught that the
  period does not reach (the yocha grant of 2009, weighed against the
  Equal Opportunities Law), its file or `data/statute-set-aside.toml` says
  it was not weighed, and why. The
  takanon's restatements give less in five places, each a card on the
  contradictions page where the law governs: maternity leave of 14 weeks
  (§1.25.5) where §6 gives 26, the absence after it only after twelve
  months' work (§7(ד) asks none), 20 check-up hours where §7(ה)'s share can
  be more, 45 days of protection from dismissal after the leave where §9
  gives 60 (§1.28.2.1), and fertility treatment protected towards a "first
  or second child" where §9(ה) counts two births with the employer.
- **The Equal Opportunities Law** (`laws/equal-opportunities-law.html`) —
  §§2, 3, 4 and 17: no discrimination between employees by sex, personal
  status or parenthood, among other grounds; a provision on pregnancy or
  birth, and a better right given to a woman, are not discrimination; a
  right connected with parenthood a mother has at her workplace — absence
  for a child's illness, a shorter day, the employer's day care or its
  share in the cost — is a father's too, where his spouse works and does not
  take it or the child is in his sole custody; and the State is an employer
  like any other (MMS-601). The documents that apply §4(א) to the day-care
  supplement — the 2011 framework's §11, the Oz LaTmura agreement's §47,
  the State teachers' day-care agreement of 10.10.2011, circular 2011-1-48
  and circular תשע"ב/5 — give a father exactly what it gives, and the
  circulars give a widower or divorcé with custody more; the takanon's
  absence for a child's illness (§1.25.3.1) gives a father the days on
  §4(א)'s own conditions. The mother's position
  gives less, each a card on the contradictions page where the law governs:
  the base agreement's "מורה אם" (§7(ג)) and the takanon's "עובדת הוראה אם"
  (§1.13.1) name no father whose spouse works and does not take her own
  shorter day, and circular תשע"ה/1, which gives such a father the shorter
  week, asks that his spouse work at least 80% and gives no route by sole
  custody. A payment to the mother in place of the shorter day, and the 10%
  mother-teacher supplement, are not rights §4(ב) lists, and §3(ב) keeps
  them hers (convention `instruments.parenthood-right`). The takanon's
  day-care supplement (§1.14) falls short of the law as of the agreement of
  10.10.2011, on that agreement's card. The 2016 framework's parents' hours
  (§18) give a father them on §4(א)'s own conditions; a provision on birth
  or nursing (the base agreement's §25, the של"ח guides' releases) is
  §3(א)'s; and a mother's supplement or release that §4(ב) does not list
  (the 1995 Oz agreement, circular תשע"ג/2's 8.3%, the takanon's §§2.1 and
  6.17, the ministry's answers page) is §3(ב)'s. Every other provision
  that names the mother teacher — her week, her hours, her rates, in the
  Ofek and Oz agreements, their circulars and the takanon — gives her what
  the definition does, and its file says the definition is weighed on the
  mother-position-fathers card; the wages commissioner's day-care updates
  change only the amounts. The takanon's transfer rules (§1.27.1.3) give
  less, a card on the contradictions page where the law governs: a
  pregnant transferee whose delivery falls within six weeks of the year's
  start is not placed, and is on unpaid leave until she is, a distinction
  on her pregnancy §2 forbids (§3(א) read as keeping only a provision that
  protects her: convention `instruments.pregnancy-provision`). Its grounds
  ב and ג give a transfer to a married woman whose husband moved: against a
  man whose wife moved, a better right §3(ב) keeps; among women, a line on
  marriage §2 forbids, which §3(ב) does not keep (convention
  `instruments.marital-status-condition`), a card as well. And the State
  teachers' long-day (יוח"א) grant of 17.5.2009 takes its share for the
  time on maternity leave or reserve duty, and for no other absence (§4.3):
  grounds §2 names, a card on the contradictions page where the law
  governs.
- **The Sick Pay Law** (`laws/sick-pay-law.html`) — §§1, 2, 4, 4א, 5, 6
  and 12: sick pay from the second day of an absence for illness (half for
  the second and third), a day and a half for each full month of work up
  to 90, no dismissal of an employee absent for his illness while his
  accrued days last, the wage it is paid on, and that a collective
  agreement's better right stands — and, by its §1, that §§2 to 6 do not
  reach an employee whose sick pay a collective agreement regulates, as a
  teacher's is (MMS-601). With it, the four laws that let an employee charge
  to his accrued sick days an absence for a family member: a child's
  illness, a child's serious illness and a child with a disability
  (`laws/sick-pay-child-law.html`), a parent's illness
  (`laws/sick-pay-parent-law.html`), a spouse's illness and malignant
  illness (`laws/sick-pay-spouse-law.html`), and a partner's pregnancy and
  birth (`laws/sick-pay-partner-pregnancy-law.html`). The takanon's
  §1.25.3.1 gives more than the Sick Pay Law on every count — 30 days a
  year, with no ceiling, and the whole salary from the first day — and its
  clauses 3, 4, 5א and 6 give what those laws give; circular תשע"ג/5's
  accrual, measured in weeks of the teacher's own timetable (convention
  `instruments.sick-days-measure`), and the two corona agreements of 2020
  are above the floor too, and the takanon's §6.5 dismissal on health
  grounds leaves §4א standing. The Oz LaTmura teachers' sick-days fund
  (renewed by the agreement of 10.9.2003) does not stand in for sick pay:
  it pays a grant only once the accrued sick days are used, when §4 has
  nothing left to give. A supplement paid on sick leave (the 2012
  local-government agreement's assistants' supplement, the takanon's stay
  supplement, §1.17) keeps §5's measure; the 2023 framework's §71, which
  cuts an hours quota with the working day, leaves §4's days whole; and the
  ministry's answer that cuts a sick teacher's pay in the next school year
  cuts it when §4's 90 days are long spent. Where a document names sick
  leave only as a condition of a grant, of seniority or of other pay, or
  rules on the redemption of unused days, which the law does not give, its
  file says it was not weighed, and why. The takanon's restatements of the family
  laws give less in four places, each a card on the contradictions page
  where the law governs: a child's malignant illness only, where the law
  gives the days for any serious illness (dialysis, or one the Minister
  names); a single parent left at 90 days where the law gives 110; 15
  additional days to assist a child with a disability where the law gives
  18; and a spouse's malignant illness charged to sick days alone, where
  the law lets the employee charge vacation days instead. And a teacher
  disqualified for health reasons retires after a share of his accrued
  sick days, or none (§1.25.3.1(7)), where §4א bars dismissing him while
  up to 90 of them last — read as a dismissal by convention
  `instruments.health-retirement-dismissal`, a card too.
- **The Annual Leave Law** (`laws/annual-leave-law.html`) — §§1–8, 10, 13,
  15, 33 and 38: 16 to 28 days of leave a year by seniority, a share of
  them for one who worked fewer than 200 days (240 in a part of the year),
  the temporary wage-earner's 4% instead, the days not counted as leave,
  when it is given and a day the employee chooses on 30 days' notice,
  accumulation and continuity, holiday pay at the regular wage, redemption
  on leaving, and that a State employee is like any other (MMS-601). The
  school recesses are read as the leave the law asks (convention
  `instruments.school-recess-as-annual-leave`) and weighed in weeks
  (convention `instruments.leave-days-measure`): the takanon's summer, 6 or
  7 days for each month of work, is above the floor for a full year and
  for every month it counts, and so are an instructor's 26 days (§8.1), an
  ulpan teacher's 60 (§14.5), a substitute's 20% or 24% (§§1.30, 2.1.8)
  against §15's 4%, the summer the strike circular תשס"ח/3 left, and the
  wage agreement of 19.10.2022's two days, which carry over no more than
  §7 does. So do the recess days the circulars move or take back (תשע"ג/1,
  תשע"ה/6, תש"פ/7, תשפ"ד/4, תשפ"ה/5) and the של"ח guides' five days of
  the supervision's enterprises (§6.17, the 1978 agreement), which leave
  the summer above §3; the concentrated-leave day charged half to the
  balance (the wages commissioner's 2023-1-13, the 2023 framework's §81);
  a supplement or allowance the takanon pays in the summer, and an expense
  it stops there, as §10(ג) counts holiday pay (§§1.9, 1.12, 3.15, 3.21,
  7.6; the 2012 local-government agreement). Where a document names leave
  only as a condition of other pay or a count, or its days rest on a rule
  outside the corpus (the civil service's quota for supervisors, §8.4, the
  1993 agreement), its file says it was not weighed, and why. Two places
  give less, each a card on the contradictions page
  where the law governs: the summer is paid only for more than 51
  consecutive workdays (§1.25.2(2א)), where §3 gives a regular teacher of
  fewer a share of the days, and their redemption; and no absence on a
  school day without the district manager's permit (§1.25.1, general 3),
  where §6(ב) lets an employee take a day of his leave on a date he
  chooses, on notice. A third is a card too, outside the teachers'
  instruments: the public-sector furlough of 18.3.2020 charges to the
  leave balance the days of an illness begun in its four weeks, giving no
  sick pay for them (§5(ט)), where §5(א)(4) counts no day of illness as
  leave.
- **The Hours of Work and Rest Law** (`laws/hours-of-work-law.html`) —
  §§1, 2, 3, 5, 6, 7, 9, 16, 17, 18, 20, 30, 31 and 35: working hours and
  overtime, a day of eight hours (seven at night and on the eve of the
  weekly rest) and a week of 45, a longer day an approved agreement may
  set, overtime and work in the weekly rest only as permitted, a weekly
  rest of 36 hours, 125% and 150% for overtime and 150% for the weekly rest
  on a regular wage with every supplement in it, the breaks, whom the law
  leaves out, and that a State employee is like any other (MMS-601). The
  law is read as reaching a teacher's hours in school and with pupils
  outside it, not his work at home, and not a principal or an inspector
  (convention `instruments.hours-law-teaching`, a pick for the lawyer).
  Within the floor: Oz LaTmura's 9-hour day, which waits on the Minister's
  approval under §5 (§62), the base agreement's 42-hour week beyond a full
  position (§33), the takanon's 140% cap on a position of up to 32 hours
  (§1.24), a kindergarten coordinator's 42 hours (circular תשפ"ו/4), the
  nursing hour on top of §20's breaks (§1.25.5), the של"ח instructor's
  Sabbath at §17's 150% (§6.17.7), the corona arrangement's day before the
  rest, and circular תשפ"ב/3's make-up hours, which may not be overtime.
  Within the floor besides: the base agreement's teacher's week of 36 hours
  (§§15, 17), a first deputy's 40 (§90) and the kindergarten's day and week
  (§§133, 142), the Oz agreement's working windows (§9) and its week beyond
  a full position (§14: five days of at most §62's nine hours), the
  takanon's guide's week of 42.5 hours (§8.1), the 1978 Shelah agreement's
  Sabbath at §17's 150%, the public-sector week shortened to 40 hours
  (17.7.2023), and the yearly kindergarten circulars' 42 hours beyond a
  full position. Most documents that name a working hour, a position or a
  break do so for something else — a sum paid pro rata to the position, a
  cap on the position across employers, a one-time grant left out of the
  hour value, a break in service, a shorter week for a mother or by age —
  and their files say they were not weighed, and why, as
  `data/statute-set-aside.toml` does for those that have no L4.
  One place gives less, a card on the contradictions page where the law
  governs: the takanon pays a day out with pupils by its end hour (§1.10),
  5 units for a day back by midnight, less than §16's premium on the hours
  beyond eight.
- **The Equal Pay Law** (`laws/equal-pay-law.html`) — §§1, 2, 3, 6, 12, 13
  and 14: equal pay and equal other remuneration for a woman and a man
  doing the same work, work equal in substance or work of equal value, the
  differences the nature of the work allows, no waiver, no weight given to
  a benefit in connection with birth or parenthood, and the State as an
  employer (MMS-601). No document of the corpus cites it. Who does the
  same work, how a term written in one sex is read, and what is weighed
  against §2 where the Equal Opportunities Law keeps a woman's better right,
  is convention `instruments.equal-pay-teaching`, a pick for the lawyer.
  The mother's position, the mother's supplement and the day-care
  participation are parenthood benefits the law leaves out (§13); they are
  weighed against the Equal Opportunities Law. Within the floor: the
  takanon's personal-car refund "על שמו או על שם אשתו" (§7.3.6.3), read for
  both sexes, and the allowances of the agreements that say every word of
  them applies to women and men alike — the kindergarten cluster managers'
  of 17.6.2021, ordinary and special education, and the ulpan teachers'
  evening supplement of 6.8.2023. Most documents the search for a sex-linked
  word finds use it for something else — ‘בעל’ for the holder of a degree,
  seniority, a post or a service car, ‘אב’ for the month of Av, ‘מזכר’ for a memorandum —
  and their files say they were not weighed, and why, as
  `data/statute-set-aside.toml` does for those that have no L4. One place
  gives less, a card on the contradictions page where
  the law governs: circular תשפ"א/6's early-retirement tracks, which put a
  woman of 55 to 57 on track B and a man of her age on track A.
- **The Advance Notice Law** (`laws/advance-notice-law.html`) — §§1–7, 10,
  11 and 12: written notice of a dismissal and of a resignation, its length
  by the months worked for an employee on a salary and for one on a wage,
  the same for a resignation, the regular wage for a notice period waived
  or not given, where no notice is owed, the State as an employer, and no
  better right taken away (MMS-601). No document of the corpus cites it.
  A dismissal the takanon dates at the school year's end takes effect on
  1 September after it, a teacher paid by grade and seniority is on a
  salary, and a longer resignation notice asked of a teacher is not below
  the floor (convention `instruments.notice-law-teaching`, a pick for the
  lawyer). Within the floor: the letter by 31 May (§§1.28.2.1(ג), 6.5;
  the Oz LaTmura agreement's annex ה') and by 30 June (§3.5, which §2.1.5
  points a kindergarten teacher to), a substitute's 3 days in his first
  two months (§6.5.7(א)), and two months' and a month's notice of
  resignation (§§1.28.1, 1.39). Most documents that name a dismissal, a
  resignation or the end of the relation do so only as the occasion of a
  payment, a fund's money or a deduction, a power to dismiss, or a strike;
  their files say they were not weighed, and why, as do the ulpan teacher
  dismissed at the end of the cycle (§14.4, silent on notice, so the law
  holds as it stands) and the colleges' procedure of 7.5.2015, which the
  corpus does not hold. Two places give
  less, each a card on the contradictions page where the law governs: a
  substitute past two months is dismissed on two weeks' notice at any
  length (§6.5.7(ב)), where §3 asks 16 days from his tenth month; and a
  teacher convicted "על מעשה פלילי" may be dismissed at once (§6.5.23(ב)),
  where the law waives notice only for a conviction that takes severance
  away.
- **The statutes the corpus cites** (`laws/index.html`) — every act the
  corpus links to, how many documents cite it, the sections it cites by
  number, and which of them the L4 pins (MMS-601). The protective statutes'
  root (`laws/root.html`) holds the floor each sets, which the root's
  precedence weighs last: where a statute gives more than the agreement, the
  circular or the takanon that would govern, the statute governs (§21 of the
  Collective Agreements Law).
- **The documents against the protective statutes** (`laws/record.html`,
  `statute-record.json`) — every document of the corpus against every
  protective statute: meets the floor, falls short of it, not weighed and
  why, or not checked (MMS-601). Each document's page shows its row, and
  each statute's page the documents weighed against it.
- **Contradictions** (`contradictions.html`) — where one instrument says one
  thing and another says another about the same pay or right: an agreement
  and the circular that implements it, a circular and the letter it executes,
  two circulars, the takanon and a newer circular or agreement, a Q&A answer
  and the takanon, and a document and what is actually paid (MMS-515,
  MMS-517). A contradiction has a side per source that gives its own answer,
  two or more, and what is PAID is a source like any document (MMS-522): the
  payslips, in general terms, and the ministry's simulator, each with what it
  pays and whether that is what the governing rule gives. A document's side
  shows a crop of its page — a scan's own pixels, a born-digital page
  rendered, or the saved web page as a browser draws it, captioned with
  file, page, resolution and pixel box, never resampled or retouched; the
  outline is drawn by the page over the picture. Each card quotes the rule
  that decides which side wins; the one filter is the kind of source. A card
  in which a paying source departs from the governing rule is an error: it
  carries a severity grade, on the findings page's scale, and a "משמעות"
  paragraph on what it means for a teacher. The crops are cut
  outside this repository from the corpus repository's sources;
  `tests/test_contradictions.py` holds each quote to the corpus and each
  crop to its file.
  THE ROOT IS THE SOURCE OF THE ROWS IT CAN SPEAK FOR (MMS-521): every
  contradiction the root finds over its grid of cases is a card, generated
  from `the contradictions report` its tests evaluate
  (`l4/tests/root-tests.l4`) — one per item, instrument that governs and
  rule, with each set of instruments that speak, the cases it settles and
  the first of them. A hand-written card attaches to such a row by key and
  cannot add one; a card the root cannot speak for says why — no pay item
  covers it yet, it is a statute's floor, it is text only, or a side is
  not an instrument the root weighs — and the suite holds the page to the
  root exactly.
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
toolchain/fetch-l4.sh          # once: installs `l4` at the pin (linux-x64, darwin-arm64; seconds)
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
