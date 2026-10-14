You are fixing L4 rules in /home/user/ofek-hadash-l4 (branch wip-mms-485 is checked out; do NOT switch branches, commit, push, or run `make`). Another agent edits OTHER files in the same checkout at the same time: touch ONLY the files named in your list (their .l4 and their findings/*.toml twin). Never edit settings.toml, tools/, tests/, CLAUDE.md, corpus/. Do NOT spawn sub-agents.

BACKGROUND. The client decided "all ambiguity decisions should follow a convention". settings.toml (read it first) holds the conventions; each has an id. Where two rules answered the same question differently, a pick was made (the client: "pick something, it's a temp setting, we can change it later"). Your job: bring each OUTLIER rule listed below into line with the picked convention.

FOR EACH ITEM:
1. Open the .l4 file and the rule named; read the corpus words it encodes (the comment beside it, and the finding). If the TEXT itself decides the point the other way (e.g. it says "כולל", "ועד בכלל", "לפחות", "לצורך הנוחות", "שנת הוותק ה-N", or sets an explicit ceiling), do NOT change the rule: record it as an EXCEPTION (below) with the words that decide it.
2. Otherwise change the rule so it applies the convention. Keep the change minimal. Update the comment beside it so it says which convention it follows ("Convention <id> (settings.toml): …"), in English.
3. If a finding records the reading (findings/<same path>.toml), rewrite its `reading` (HEBREW, an L4 identifier stays in backticks) to the new reading, and set/replace its `convention = "<id>"` line (placed just before its `l4 =` line). Any finding kind may carry `convention`. Do not change `quote`, `keys`, `id`. If the finding's `evidence` boolean depended on the old reading and no longer holds, adjust the evidence definitions so it is TRUE while the defect is in the TEXT (the evidence shows the text's flaw, not our reading).
4. Run `l4 /home/user/ofek-hadash-l4/<file> --fixed-now 2026-06-01T00:00:00Z` (from anywhere) and make sure there are no errors and every #ASSERT is true. An #ASSERT that reproduced the OLD reading's numbers must be updated to the new reading (or, if it reproduces a figure the TEXT prints, keep it and compare with rounding in the assert only). Never delete an assert to get green; never leave a red one.
5. Also tag with `convention = "<id>"` any OTHER finding in your files whose reading applies one of the conventions you touch (only where clearly so).

WHAT TO RETURN. Write JSON to the path given below, saved incrementally after each item:
{"applies": {"<convention id>": [{"l4": "l4/…", "rule": "<exact L4 name of a DECIDE/MEANS/DECLARE that applies it, verbatim, no backticks>"}…]},
 "exceptions": {"<convention id>": [{"l4": "...", "rule": "...", "value": "<HEBREW: what this rule does instead, short>", "why": "<HEBREW: the words of the text that decide it>"}]},
 "changed": [{"item": n, "l4": "...", "rule": "...", "what": "<one English line>", "finding": "<id or null>"}],
 "skipped": [{"item": n, "why": "..."}]}
For "applies", list the rules that apply each convention you dealt with — BOTH the outliers you fixed AND the rules on the side that already followed it (named in your items). Each rule name must appear verbatim as a definition in that file (DECIDE `x`, `x` MEANS, DECLARE `x`, ASSUME `x`, or a record field `x` IS A …). Then reply with a short summary.
