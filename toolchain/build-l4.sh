#!/usr/bin/env bash
# Build the `l4` CLI at the revision pinned in toolchain/L4_COMMIT.
# legalese/l4-ide publishes no Linux binary (its VSIX ships macOS and
# Windows only), so it is built from source: GHC (toolchain/GHC_VERSION)
# via ghcup, then `cabal build exe:l4`. Cold, that is 30-60 minutes on four
# cores; the cabal store makes later builds minutes.
#
#   toolchain/build-l4.sh [DEST]     # installs to DEST (default ~/.local/bin/l4)
set -euo pipefail
export LANG=C.UTF-8 LC_ALL=C.UTF-8
here="$(cd "$(dirname "$0")" && pwd)"
commit="$(cat "$here/L4_COMMIT")"
ghc_version="$(cat "$here/GHC_VERSION")"
dest="${1:-$HOME/.local/bin/l4}"
src="${L4_SRC:-$HOME/.cache/l4-ide}"

# a GHC of the pinned version already on PATH (CI's haskell-actions/setup)
# is used as it is; otherwise ghcup installs one
export PATH="$HOME/.ghcup/bin:$PATH"
if [ "$(ghc --numeric-version 2>/dev/null)" != "$ghc_version" ] || ! command -v cabal >/dev/null; then
  if ! command -v ghcup >/dev/null; then
    export BOOTSTRAP_HASKELL_NONINTERACTIVE=1 BOOTSTRAP_HASKELL_MINIMAL=1
    curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh
  fi
  ghcup install ghc "$ghc_version" --set
  ghcup install cabal latest --set
fi

if [ ! -d "$src/.git" ]; then
  git clone --filter=blob:none https://github.com/legalese/l4-ide "$src"
fi
git -C "$src" fetch --depth 1 origin "$commit"
git -C "$src" checkout --detach "$commit"

cd "$src"
cabal update
cabal build -j exe:l4 --disable-tests --disable-documentation
mkdir -p "$(dirname "$dest")"
cp "$(cabal list-bin exe:l4)" "$dest"
# the binary's embedded-library fallback finds nothing at this revision, so
# IMPORT prelude resolves only from disk: install the libraries where l4
# looks (its XDG data dir)
libs="${XDG_DATA_HOME:-$HOME/.local/share}/jl4/libraries"
mkdir -p "$libs"
cp "$src"/jl4-core/libraries/*.l4 "$libs"/
"$dest" --help | head -1
echo "installed $dest at legalese/l4-ide@$commit"
