"""Check l4/simulator/educalc-ofek-hadash.l4 against the simulator's recorded
answers (MMS-523): every recorded request, every line, to the agora.

    python3 tools/simulator_check.py PATH/TO/capture/cache.jsonl[.gz]

The recording is the private extraction of the ministry's simulator (MMS-512,
the corpus repository's branch claude/mms-512-educalc-extraction,
reference/educalc-extraction_2026-10-20/capture/). It stays outside this
repository: this tool reads it, runs the module's @export on every Ofek
Hadash request of salary month 2026-09 (an #EVAL per request), and writes
data/simulator-validation.json — the counts per pay code and every residual,
each with the request's non-empty fields and the two amounts. Nothing is
fitted: a line the module does not reproduce is listed, never tolerated.
"""
from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import modules  # noqa: E402

MODULE = ROOT / "l4" / "simulator" / "educalc-ofek-hadash.l4"
OUT = ROOT / "data" / "simulator-validation.json"
MONTH = 202609
CALC = "ofekHadash"
TOTAL = 9999          # the simulator's gross line: a sum, not a rule
AGORA = Decimal("0.01")

# The request's fields, as the module's `educalc request` declares them.
FIELDS = ["DERUG_OFEK", "DARGA1", "VETEK", "VETEK_ZHL", "MEKADEM_MISRA_REFORMA",
          "KOD_TAFKID_2", "KOD_TAFKID_3", "AHUZ_BAGRUT", "KURS_HM", "RETZIFUT_MATYA",
          "MEKADEM_HM_NAMUCH", "MEKADEM_HM_GAVOHA", "MEKADEM_HM_SHILUV",
          "AHUZ_AUTISTIC_PARA", "AHUZ_AUTISTIC_HM", "MEKADEM_HADRACHA", "RAKAZ_1",
          "RAKAZ_2", "GMUL_NIHUL_NIGRAR", "OFEK_TAFKID", "VETEK_NIHUL",
          "AHUZ_GANENET_AMITA", "GMUL_YIUTZ_NIGRAR", "IS_SHAOT_YEUTZ",
          "MIS_SHAOT_YEUTZ", "MIS_SHAOT_YEUTZ_FRONT", "MIS_SHAOT_SHVUIYOT",
          "GMUL_MISRA_MECHUNANIM", "MIS_HONCHIM"]


def number(v) -> float | int:
    try:
        d = Decimal(str(v))
    except Exception:
        return 0
    return int(d) if d == d.to_integral_value() else float(d)


def requests(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        recs = [json.loads(l) for l in f if l.strip()]
    return [r for r in recs if r.get("calc") == CALC and r.get("lines")
            and r["payload"].get("DATE_SACHAR") == MONTH]


def by_code(lines) -> dict[int, Decimal]:
    out: dict[int, Decimal] = defaultdict(Decimal)
    for code, amount in lines:
        if int(code) != TOTAL:
            out[int(code)] += Decimal(str(amount))
    return dict(out)


CHUNK = 500   # requests per generated file: one check of the module per file
LINE_RE = re.compile(r"`educalc line` OF (-?[\d.]+), (-?[\d.]+)")


def literal(payload: dict) -> str:
    return "`educalc request` " + " ".join(str(number(payload.get(k, 0))) for k in FIELDS)


def answers(payloads: list[dict]) -> list[list[tuple[int, Decimal]]]:
    """The module's answer to each request, by one #EVAL per request in a
    generated file that imports it (`l4 batch` checks the module again for
    every row, minutes a row, so it cannot carry thousands)."""
    out: list[list[tuple[int, Decimal]]] = []
    with tempfile.TemporaryDirectory() as d:
        for i in range(0, len(payloads), CHUNK):
            part = payloads[i:i + CHUNK]
            src = Path(d) / "educalc-recorded-requests.l4"
            src.write_text("IMPORT prelude\nIMPORT `educalc-ofek-hadash`\n\n" + "".join(
                f"#EVAL `the simulator's answer to` ({literal(p)})\n" for p in part), encoding="utf-8")
            r = subprocess.run(["l4", "run", "--json", src.name], cwd=d, env=modules.env(),
                               capture_output=True, text=True)
            data = json.loads(r.stdout)
            results = [x for x in data.get("results", []) if x.get("kind") == "value"]
            if not data.get("ok") or len(results) != len(part):
                raise SystemExit(f"l4 run failed on requests {i}..{i + len(part)}:\n"
                                 f"{r.stdout[:2000]}{r.stderr[:2000]}")
            results.sort(key=lambda x: int(str(x["range"]).split(":")[1]))
            for x in results:
                out.append([(int(c), Decimal(a)) for c, a in LINE_RE.findall(str(x["value"]))])
            print(f"  {i + len(part)}/{len(payloads)}", flush=True)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    recs = requests(Path(argv[1]))
    results = answers([r["payload"] for r in recs])
    assert len(results) == len(recs), (len(results), len(recs))
    seen: Counter = Counter()
    exact: Counter = Counter()
    residuals = []
    whole = 0
    for rec, res in zip(recs, results):
        sim = by_code((l["Semel"], l["Scum"]) for l in rec["lines"])
        ours = by_code(res)
        ok = True
        for code in sorted(set(sim) | set(ours)):
            a, b = sim.get(code, Decimal(0)), ours.get(code, Decimal(0))
            seen[code] += 1
            if a == b:
                exact[code] += 1
                continue
            ok = False
            residuals.append({
                "inputs": {k: number(v) for k, v in sorted(rec["payload"].items())
                           if k in FIELDS and number(v) != 0},
                "code": code, "simulator": str(a), "l4": str(b), "difference": str(b - a),
                "kind": "one agora" if abs(b - a) == AGORA else "more"})
        whole += ok
    data = {
        "module": str(MODULE.relative_to(ROOT)),
        "calculator": CALC, "salary_month": "2026-09", "issue": "MMS-523",
        "requests": len(recs), "requests_reproduced": whole,
        "codes": {str(c): {"lines": seen[c], "exact": exact[c]} for c in sorted(seen)},
        "residuals": residuals,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{whole}/{len(recs)} requests reproduced to the agora; {len(residuals)} residual lines")
    for c in sorted(seen):
        if exact[c] != seen[c]:
            print(f"  {c:>5} {exact[c]}/{seen[c]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
