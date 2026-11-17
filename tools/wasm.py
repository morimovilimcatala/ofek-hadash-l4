"""The L4 evaluator as WebAssembly, which the calculator page, the findings'
traces and the calculator's tests run (MMS-776).

    WASM     build/l4wasm/l4.wasm, put there by toolchain/fetch-wasm.sh
    GLUE     tools/assets/l4wasm/l4.mjs, GHC's JavaScript glue for it (committed)

`fetch()` runs toolchain/fetch-wasm.sh, which downloads the release
toolchain/L4_WASM_RELEASE names and refuses any bytes but the pinned
sha256, so the 21 MB file is not committed to history at each rebuild;
build/l4wasm/ keeps it, so it is fetched once per machine.
"""
from __future__ import annotations

import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WASM = ROOT / "build" / "l4wasm" / "l4.wasm"
GLUE = ROOT / "tools" / "assets" / "l4wasm" / "l4.mjs"
FETCH = ROOT / "toolchain" / "fetch-wasm.sh"


@lru_cache(maxsize=None)
def fetch() -> Path | None:
    """The checked wasm, or None where it cannot be had (it says why)."""
    r = subprocess.run(["bash", str(FETCH)], capture_output=True, text=True, env=None)
    if r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    return WASM if r.returncode == 0 and WASM.exists() else None
