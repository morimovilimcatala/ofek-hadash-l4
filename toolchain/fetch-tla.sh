#!/usr/bin/env bash
# Put TLC, the TLA+ model checker, at build/tla2tools.jar (MMS-804): the
# tlaplus release named below, checked against its pinned sha256. Any other
# bytes are refused; nothing else is installed. tools/hunt.py's `tla` hunter
# runs it with `java` on the models `l4 explore --emit` writes, and leaves
# the hunter out where the jar or java is missing.
#
#   toolchain/fetch-tla.sh          # prints the path of the checked jar
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$here")"
version="v1.8.0"
want="67f9575c3b9ef7a0787b1bded34812862ffe79d711298e5a75b1a77720b19928"
dest="${TLA2TOOLS:-$root/build/tla2tools.jar}"

sha() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
die() { echo "fetch-tla: $*" >&2; exit 1; }

mkdir -p "$(dirname "$dest")"
if [ -f "$dest" ] && [ "$(sha "$dest")" = "$want" ]; then
  echo "$dest"
  exit 0
fi
curl -fsSL --retry 4 -o "$dest.part" \
  "https://github.com/tlaplus/tlaplus/releases/download/$version/tla2tools.jar" \
  || die "could not download tla2tools.jar $version"
got="$(sha "$dest.part")"
[ "$got" = "$want" ] || { rm -f "$dest.part"; die "tla2tools.jar $version has sha256 $got, this script pins $want"; }
mv "$dest.part" "$dest"
echo "$dest"
