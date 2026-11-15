"""Inventory every DEONTIC rule in the repo's L4 files: file, name, inputs."""
import json, re, sys
from pathlib import Path

repo = Path(sys.argv[1]); L4 = repo / "l4"
rows = []
for f in sorted(L4.rglob("*.l4")):
    if f.is_symlink() or "modules" in f.relative_to(L4).parts[:1]:
        continue
    lines = f.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"\s*GIVETH\s+A\s+DEONTIC\b", ln):
            # walk back over GIVEN lines (possibly continued) to the previous blank/@ line
            j = i - 1; given = []
            while j >= 0 and lines[j].strip() and not lines[j].lstrip().startswith(("@", "--", "§")):
                given.insert(0, lines[j].strip()); j -= 1
            # forward to DECIDE / name
            k = i + 1
            while k < len(lines) and not re.match(r"\s*(DECIDE|DEFINE|MEANS)\b|^\s*`", lines[k]) and k < i + 4:
                k += 1
            m = re.search(r"(?:DECIDE|DEFINE)\s+(`[^`]+`|\S+)", lines[k] if k < len(lines) else "")
            g = " ".join(given)
            inputs = []
            if g.startswith("GIVEN"):
                for part in re.split(r",\s*(?![^`]*`\s*(?:,|$))", g[5:]):
                    mm = re.match(r"\s*(`[^`]+`|\S+)\s+IS\s+(?:A|AN)\s+(.+)", part)
                    if mm:
                        inputs.append([mm.group(1), mm.group(2).strip()])
                    else:
                        inputs.append([part.strip(), "?"])
            rows.append({"file": str(f.relative_to(L4)), "line": i + 1,
                         "name": m.group(1) if m else None, "given": g, "inputs": inputs,
                         "deontic": ln.strip()})
json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)
