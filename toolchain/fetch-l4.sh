#!/usr/bin/env bash
# Install the `l4` CLI at toolchain/L4_COMMIT from legalese/prereleases,
# Legalese's shelf of standalone builds from l4-ide `unstable` (MMS-558).
# The release is the one toolchain/L4_SHELF names; the archive is checked
# against the sha256 pinned there and its BUILD-INFO.txt against the pin.
# Any mismatch stops the install: there is no fallback to another build.
# Native on linux-x64 and darwin-arm64, in seconds.
#
#   toolchain/fetch-l4.sh [DEST]     # installs to DEST (default ~/.local/bin/l4)
#
# toolchain/build-l4.sh builds the same commit from source (30-60 min cold);
# it stays for a commit the shelf has no release for (measure-compiler.yml).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
commit="$(cat "$here/L4_COMMIT")"
dest="${1:-$HOME/.local/bin/l4}"
shelf="$here/L4_SHELF"

field() { awk -v k="$1" '$1 == k { print $2 }' "$shelf"; }
die() { echo "fetch-l4: $*" >&2; exit 1; }

tag="$(field tag)"
[ -n "$tag" ] || die "no tag in $shelf"
case "$tag" in
  unstable-????????-"${commit:0:7}"|unstable-????????-"${commit:0:7}"-*) ;;
  *) die "$shelf names $tag, which is not a build of L4_COMMIT ${commit:0:7}" ;;
esac

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) platform=linux-x64 ;;
  Darwin-arm64) platform=darwin-arm64 ;;
  *) die "no shelf build for $(uname -s)-$(uname -m); use toolchain/build-l4.sh" ;;
esac
want="$(field "$platform")"
[ -n "$want" ] || die "$shelf pins no sha256 for $platform"

name="l4-$tag-$platform"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/l4-shelf"
archive="$cache/$name.tar.gz"
mkdir -p "$cache"
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
if [ ! -f "$archive" ] || [ "$(sha "$archive")" != "$want" ]; then
  url="https://github.com/legalese/prereleases/releases/download/$tag/$name.tar.gz"
  curl -fsSL --retry 4 -o "$archive.part" "$url" || die "could not download $url"
  mv "$archive.part" "$archive"
fi
got="$(sha "$archive")"
[ "$got" = "$want" ] || die "$name.tar.gz has sha256 $got, $shelf pins $want"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -xzf "$archive" -C "$work"
built="$(awk '$1 == "commit" { print $2 }' "$work/$name/BUILD-INFO.txt")"
[ "$built" = "$commit" ] || die "$name was built from $built, not L4_COMMIT $commit"

mkdir -p "$(dirname "$dest")"
cp "$work/$name/l4" "$dest"
chmod +x "$dest"
# l4 resolves IMPORT prelude from disk, not from the binary: install the
# libraries the archive carries, built at the same commit, where l4 looks
libs="${XDG_DATA_HOME:-$HOME/.local/share}/jl4/libraries"
mkdir -p "$libs"
cp "$work/$name/libraries/"*.l4 "$libs/"
"$dest" --help | head -1
echo "installed $dest from legalese/prereleases $tag ($platform)"
