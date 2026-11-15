"""Time `l4 run --json` on given files, one at a time, on two builds,
alternating, recording wall clock and peak RSS (wait4's ru_maxrss).

  python3 timings.py REPO OUT.json OLD_EXE OLD_XDG|- NEW_EXE NEW_XDG FILE...
"""
import json, os, subprocess, sys, time
from pathlib import Path

repo = Path(sys.argv[1]).resolve(); outp = sys.argv[2]
builds = [("pinned c9a3fe3", sys.argv[3], sys.argv[4]), ("2818cc2", sys.argv[5], sys.argv[6])]
sys.path.insert(0, str(repo / "tools"))
import l4run, modules  # noqa: E402
res = []
for f in sys.argv[7:]:
    p = Path(f).resolve()
    for name, exe, xdg in builds:
        env = modules.env()
        if xdg != "-":
            env["XDG_DATA_HOME"] = xdg
        t0 = time.monotonic()
        dump = Path(outp).parent / "timing-out" / f"{name.split()[0]}--{p.name}.json"
        dump.parent.mkdir(exist_ok=True)
        fh = open(dump, "w")
        pr = subprocess.Popen([exe, "run", "--json", f"--fixed-now={l4run.FIXED_NOW}", p.name],
                              cwd=p.parent, env=env, stdout=fh, stderr=subprocess.DEVNULL)
        _, status, ru = os.wait4(pr.pid, 0)
        wall = time.monotonic() - t0
        fh.close()
        r = {"file": str(p.relative_to(repo)), "build": name, "wall": round(wall, 1),
             "cpu": round(ru.ru_utime + ru.ru_stime, 1), "peak_gb": round(ru.ru_maxrss / 2**20, 2),
             "status": status}
        res.append(r); print(r, flush=True)
json.dump(res, open(outp, "w"), indent=1)
