"""Dig into explore results: the candidate never-should-happen states in
graphs whose partiality cannot explain them."""
import collections, json, re, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
def graphs(r):
    for t in r["trials"]:
        if t.get("graph"):
            yield f"{t['rule']} {t['args']}".strip(), t["graph"], t.get("line")
    for g in (r.get("trace") or {}).get("graphs") or []:
        yield "#TRACE " + g["contract"], g, None
def isbreach(s): return "BREACH" in s["residual"].split("\n")[0]
def isfulfilled(s): return s["residual"].strip().startswith("FULFILLED")
cls = collections.Counter(); out = collections.defaultdict(list)
for r in rows:
    for o, g, line in graphs(r):
        c = g["coverage"]
        why = [u["why"] for u in c["untried"]]
        kinds = set()
        if c["refused"]: kinds.add("refused")
        if any("no WITHIN" in w for w in why): kinds.add("no-within")
        if any("not a literal" in w for w in why): kinds.add("nonliteral-within")
        if any("Internal error" in w for w in why): kinds.add("internal-error")
        if c["stops"]: kinds.add("bounded")
        cls[tuple(sorted(kinds)) or ("complete",)] += 1
        st = {s["id"]: s for s in g["states"]}
        outs = collections.defaultdict(list)
        for t in g["transitions"]:
            if t["kind"] != "terminal":
                outs[t["from"]].append(t)
        res0 = g["states"][0]["residual"]
        hasmust = bool(re.search(r"\bMUST\b(?! NOT)", res0))
        noisy = bool(kinds & {"refused", "internal-error"})
        if not noisy and hasmust and not any(isfulfilled(s) for s in g["states"]):
            out["MUST at outset, FULFILLED never reached"].append((r["file"], o, g))
        for s in g["states"]:
            o2 = outs[s["id"]]
            if not noisy and not s["terminal"] and not o2:
                out["stuck"].append((r["file"], o, g, s))
            if not noisy and o2 and all(t["kind"] == "tick" for t in o2) and re.search(r"\bMUST\b", s["residual"].split("LEST")[0]) and all(isbreach(st[t["to"]]) for t in o2):
                out["owed, only the deadline into breach"].append((r["file"], o, g, s))
            ticks = [t for t in o2 if t["kind"] == "tick"]
            if len({t["label"] for t in ticks}) > 1:
                out["two ticks"].append((r["file"], o, g, s))
        # self-renewing with no exit except breach: every cycle
        if not noisy and any(t["kind"] != "terminal" and t["from"] == t["to"] for t in g["transitions"]):
            out["act loops to the same state (renews forever)"].append((r["file"], o, g))
print("classes", cls.most_common())
for k, v in out.items():
    files = sorted({x[0] for x in v})
    print(f"\n== {k}: {len(v)} graphs/states in {len(files)} files")
    seen = set()
    for x in v:
        if (x[0], x[1]) in seen: continue
        seen.add((x[0], x[1]))
        s = x[3] if len(x) > 3 else None
        print("  ", x[0], "|", x[1][:90], "|", (s["residual"][:260].replace("\n", " ") + " || path: " + "; ".join(s["path"])[:300]) if s else x[2]["states"][0]["residual"][:260].replace("\n", " "))
        if len(seen) >= int(sys.argv[2] if len(sys.argv) > 2 else 15): break
