#!/usr/bin/env bash
# Put the pinned l4.wasm at build/l4wasm/l4.wasm (MMS-776): the release
# toolchain/L4_WASM_RELEASE names, of this repository, checked against the
# sha256 pinned there. Any other bytes are refused; nothing is installed.
# `make site`, the calculator's tests, the findings' traces and CI all read
# the wasm from there, so the 21 MB file is downloaded once per machine
# rather than committed to history at every rebuild.
#
#   toolchain/fetch-wasm.sh          # prints the path of the checked wasm
#
# Where it comes from: build/l4wasm/l4.wasm if it already has the pinned
# sha256, else the release. Nothing else is accepted.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
pins="$here/L4_WASM_RELEASE"
repo="morimovilimcatala/ofek-hadash-l4"

field() { awk -v k="$1" '$1 == k { print $2 }' "$pins"; }
die() { echo "fetch-wasm: $*" >&2; exit 1; }
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }

tag="$(field tag)"
want="$(field sha256)"
[ -n "$tag" ] && [ -n "$want" ] || die "$pins names no tag or no sha256"
commit="$(cat "$here/L4_WASM_COMMIT")"
patch_sha="$(sha "$here/wasm-trace.patch")"
[ "$tag" = "l4wasm-${commit:0:7}-${patch_sha:0:7}" ] \
  || die "$pins names $tag, which is not a build of L4_WASM_COMMIT ${commit:0:7} with wasm-trace.patch ${patch_sha:0:7}"

dir="${L4_WASM_DIR:-$root/build/l4wasm}"
dest="$dir/l4.wasm"
mkdir -p "$dir"
if [ -f "$dest" ] && [ "$(sha "$dest")" = "$want" ]; then
  echo "$dest"
  exit 0
fi

url="https://github.com/$repo/releases/download/$tag/l4.wasm"
if curl -fsSL --retry 4 -o "$dest.part" "$url" 2>/dev/null; then
  got="$(sha "$dest.part")"
  [ "$got" = "$want" ] || { rm -f "$dest.part"; die "$url has sha256 $got, $pins pins $want"; }
  mv "$dest.part" "$dest"
  echo "$dest"
  exit 0
fi
rm -f "$dest.part"

die "could not download $url"
