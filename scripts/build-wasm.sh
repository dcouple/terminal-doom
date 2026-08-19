#!/usr/bin/env bash
# Build the DOOM wasm artifacts that web/ ships.
#
# The engine is Chocolate Doom by way of cloudflare/doom-wasm, the port that
# already carries the emscripten glue for video, sound and input. This builds it
# at a pinned commit with a pinned emscripten, applies scripts/patch-doom-wasm.py,
# and copies three files into web/.
#
# Nobody playing terminal-doom runs this — web/doom.js, web/doom.wasm and
# web/doom1.wad are committed. Run it to move the engine forward.
#
# Needs: git, autoconf, automake, pkgconf   (brew install automake pkgconf)
set -euo pipefail

DOOM_WASM_REPO="https://github.com/cloudflare/doom-wasm.git"
DOOM_WASM_REF="${DOOM_WASM_REF:-main}"
EMSDK_VERSION="${EMSDK_VERSION:-3.1.64}"

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$ROOT/web"
BUILD="${BUILD_DIR:-$ROOT/.build}"
mkdir -p "$BUILD"

need() { command -v "$1" >/dev/null 2>&1 || { echo "build-wasm: missing $1" >&2; exit 1; }; }
need git
need autoreconf
need make
need python3
# configure.ac calls PKG_CHECK_MODULES, and without pkg.m4 on aclocal's path
# autoconf fails with a confusing "undefined or overquoted macro" further up.
[ -f "$(aclocal --print-ac-dir)/pkg.m4" ] || echo "build-wasm: warning, pkg.m4 not found (brew install pkgconf)" >&2

# --- emscripten -------------------------------------------------------------
# A pinned emsdk rather than whatever emcc is on PATH: the port predates several
# flag renames, and newer toolchains reject it outright.
if [ "${USE_SYSTEM_EMCC:-0}" = "1" ]; then
  need emcc
  echo "build-wasm: using $(command -v emcc) instead of the pinned toolchain"
else
  EMSDK_DIR="${EMSDK_DIR:-$BUILD/emsdk}"
  if [ ! -d "$EMSDK_DIR" ]; then
    git clone --depth 1 https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
  fi
  (cd "$EMSDK_DIR" && ./emsdk install "$EMSDK_VERSION" && ./emsdk activate "$EMSDK_VERSION")
  # shellcheck disable=SC1091
  source "$EMSDK_DIR/emsdk_env.sh" >/dev/null 2>&1
  need emcc
fi

# --- source -----------------------------------------------------------------
SRC="$BUILD/doom-wasm"
if [ ! -d "$SRC/.git" ]; then
  git clone "$DOOM_WASM_REPO" "$SRC"
fi
git -C "$SRC" fetch --all --quiet
git -C "$SRC" checkout --quiet "$DOOM_WASM_REF"
git -C "$SRC" reset --hard --quiet
git -C "$SRC" clean -xfdq

python3 "$ROOT/scripts/patch-doom-wasm.py" "$SRC"

# The port loads the iwad through the emscripten filesystem, so it has to sit
# beside the build output for createPreloadedFile to find it.
cp "$WEB/doom1.wad" "$SRC/src/doom1.wad"

# --- build ------------------------------------------------------------------
cd "$SRC"
emconfigure autoreconf -fiv
# --without-* stops configure from finding the host's libsamplerate and libpng
# through pkg-config and then trying to link them into the wasm.
ac_cv_exeext=".html" emconfigure ./configure --host=none-none-none \
  --without-libsamplerate --without-libpng
emmake make -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"

# --- install ----------------------------------------------------------------
for f in doom.js doom.wasm; do
  [ -f "$SRC/src/$f" ] || { echo "build-wasm: $f was not produced" >&2; exit 1; }
  cp "$SRC/src/$f" "$WEB/$f"
done
# web/default.cfg is ours — it rebinds the keys — so it is not copied back over.

{
  echo "engine:     cloudflare/doom-wasm $(git -C "$SRC" rev-parse HEAD)"
  echo "emscripten: $EMSDK_VERSION"
  echo "built:      $(date -u +%Y-%m-%d)"
} > "$WEB/BUILD-INFO"

echo
/bin/cat "$WEB/BUILD-INFO"
ls -lh "$WEB/doom.js" "$WEB/doom.wasm"
