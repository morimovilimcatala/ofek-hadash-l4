#!/usr/bin/env bash
# Build the L4 evaluator as WebAssembly for the site's salary calculator, at
# the revision pinned in toolchain/L4_WASM_COMMIT with toolchain/wasm-trace.patch
# applied, and write it to tools/assets/l4wasm/ with BUILD.toml beside it.
#
# The wasm has its own pin (MMS-535): l4-ide `unstable`, which loads a module
# two importers share (#649) and keeps one copy of each module whatever the
# number of paths to it (#573/#575), so the root loads. toolchain/L4_COMMIT,
# the CLI's pin, moves to `unstable` on its own, after every file is checked
# with it. The patch adds `l4_eval_files` (the imports as files), the trace
# JSON of #EVALTRACE, and the reuse of one call's type-checked imports by the
# next call on the same imports.
#
# The toolchain is GHC's WASM backend from ghc-wasm-meta, pinned to the
# commit in toolchain/GHC_WASM_META (flavour 9.10, as legalese/l4-ide's own
# CI uses); it is a set of prebuilt bindists (~5 GB, minutes to fetch). The
# build itself compiles jl4-core and every dependency for wasm32-wasi: about
# an hour cold on four cores, minutes once the WASM cabal store is warm.
#
#   toolchain/build-wasm.sh [DEST]     # default tools/assets/l4wasm
#   WASM_JOBS=4 toolchain/build-wasm.sh  # fewer parallel jobs, for a small machine
set -euo pipefail
export LANG=C.UTF-8 LC_ALL=C.UTF-8
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
commit="$(cat "$here/L4_WASM_COMMIT")"
read -r meta flavour < "$here/GHC_WASM_META"
patch="$here/wasm-trace.patch"
dest="${1:-$root/tools/assets/l4wasm}"
src="${L4_WASM_SRC:-$HOME/.cache/l4-ide-wasm}"
prefix="${GHC_WASM_PREFIX:-$HOME/.ghc-wasm}"

# the toolchain, from the pinned ghc-wasm-meta (its bootstrap.sh fetches
# master, which would move under us)
if [ ! -f "$prefix/env" ]; then
  tmp="$(mktemp -d)"
  curl -f -L --retry 5 \
    "https://gitlab.haskell.org/haskell-wasm/ghc-wasm-meta/-/archive/$meta/ghc-wasm-meta-$meta.tar.gz" \
    | tar xz --strip-components=1 -C "$tmp"
  PREFIX="$prefix" FLAVOUR="$flavour" bash "$tmp/setup.sh"
  rm -rf "$tmp"
fi
# shellcheck disable=SC1091
source "$prefix/env"

# the source at the pin, with the patch and nothing else
if [ ! -d "$src/.git" ]; then
  git clone --filter=blob:none https://github.com/legalese/l4-ide "$src"
fi
git -C "$src" fetch --depth 1 origin "$commit" 2>/dev/null || true
git -C "$src" checkout --detach --force "$commit"
git -C "$src" reset --hard "$commit"
git -C "$src" apply "$patch"

cd "$src"
wasm32-wasi-cabal update
wasm32-wasi-cabal build -j"${WASM_JOBS:-}" jl4-wasm --project-file=cabal-wasm.project
wasm="$(find dist-newstyle/build/wasm32-wasi -path '*/jl4-wasm/jl4-wasm.wasm' -type f | head -1)"
"$(wasm32-wasi-ghc --print-libdir)/post-link.mjs" -i "$wasm" -o dist-newstyle/jl4-wasm.mjs
wasm-opt -Oz "$wasm" -o dist-newstyle/jl4-wasm.opt.wasm

mkdir -p "$dest"
cp dist-newstyle/jl4-wasm.opt.wasm "$dest/l4.wasm"
cp dist-newstyle/jl4-wasm.mjs "$dest/l4.mjs"
sha() { sha256sum "$1" | cut -d' ' -f1; }
cat > "$dest/BUILD.toml" <<EOF
# Written by toolchain/build-wasm.sh; do not edit. The site's calculator runs
# l4.wasm (+ the l4.mjs glue GHC's post-link.mjs writes for it).
l4_commit = "$commit"
patch = "toolchain/wasm-trace.patch"
patch_sha256 = "$(sha "$patch")"
ghc = "$(wasm32-wasi-ghc --numeric-version)"
ghc_wasm_meta = "$meta"
wasm_opt = "$(wasm-opt --version)"
unoptimized_bytes = $(stat --format=%s "$wasm")

[files]
"l4.wasm" = "$(sha "$dest/l4.wasm")"
"l4.mjs" = "$(sha "$dest/l4.mjs")"
EOF
ls -l "$dest"
echo "built $dest from legalese/l4-ide@$commit + $(basename "$patch")"
