#!/usr/bin/env bash
# Build the `l4` CLI at the revision pinned in toolchain/L4_COMMIT.
# legalese/l4-ide publishes no Linux binary (its VSIX ships macOS and
# Windows only), so it is built from source: GHC (toolchain/GHC_VERSION)
# via ghcup, then `cabal build exe:l4`. Cold, that is 30-60 minutes on four
# cores; the cabal store makes later builds minutes.
#
#   toolchain/build-l4.sh [DEST]     # installs to DEST (default ~/.local/bin/l4)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
commit="$(cat "$here/L4_COMMIT")"
ghc_version="$(cat "$here/GHC_VERSION")"
dest="${1:-$HOME/.local/bin/l4}"
src="${L4_SRC:-$HOME/.cache/l4-ide}"

if ! command -v ghcup >/dev/null && [ ! -x "$HOME/.ghcup/bin/ghcup" ]; then
  export BOOTSTRAP_HASKELL_NONINTERACTIVE=1 BOOTSTRAP_HASKELL_MINIMAL=1
  curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh
fi
export PATH="$HOME/.ghcup/bin:$PATH"
ghcup install ghc "$ghc_version" --set
ghcup install cabal latest --set

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
"$dest" --help | head -1
echo "installed $dest at legalese/l4-ide@$commit"
