#!/usr/bin/env bash
# terminal-doom installer.
#
#   curl -fsSL https://terminal-doom.sh/install | bash        (once the domain is up)
#   curl -fsSL https://raw.githubusercontent.com/dcouple/terminal-doom/main/install.sh | bash
#
# Pulls the terminal-doom tree out of the repo, installs terminal-browser if it
# is not already here, and drops a terminal-doom on your PATH.
set -euo pipefail

REPO="${TERMINAL_DOOM_REPO:-dcouple/terminal-doom}"
BRANCH="${TERMINAL_DOOM_BRANCH:-main}"
LIB_HOME="${XDG_DATA_HOME:-$HOME/.local/lib}"
BIN_HOME="${XDG_BIN_HOME:-$HOME/.local/bin}"
APP="${TERMINAL_DOOM_INSTALL_ROOT:-$HOME/.local/lib/terminal-doom}"

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) echo "terminal-doom needs macOS or Linux (the kitty graphics protocol is thin on Windows)" >&2; exit 1 ;;
esac

for tool in curl tar; do
  command -v "$tool" >/dev/null 2>&1 || { echo "terminal-doom: $tool is required" >&2; exit 1; }
done

echo "terminal-doom"

# --- terminal-browser -------------------------------------------------------
# It does the actual work of putting chromium pixels in the terminal, so it is
# not optional. Installing it also gets us a javascript runtime for free.
if ! command -v terminal-browser >/dev/null 2>&1 && [ ! -x "$BIN_HOME/terminal-browser" ]; then
  echo "  installing terminal-browser first"
  curl -fsSL https://terminal-browser.sh/install | bash
fi

# --- the game ---------------------------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "  downloading terminal-doom"
curl -fsSL --retry 3 --retry-delay 2 \
  "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" \
  | tar -xz -C "$TMP" --strip-components=1

[ -f "$TMP/web/doom.wasm" ] || { echo "terminal-doom: the download is missing the game" >&2; exit 1; }

# Unpack beside the target and rename over it, so a failed install never leaves
# half a tree behind.
mkdir -p "$(dirname "$APP")"
rm -rf "$APP.new" "$APP.old"
mv "$TMP" "$APP.new"
trap - EXIT
[ -d "$APP" ] && mv "$APP" "$APP.old"
mv "$APP.new" "$APP"
rm -rf "$APP.old"
chmod +x "$APP/bin/terminal-doom" "$APP/scripts/"*.sh 2>/dev/null || true

mkdir -p "$BIN_HOME"
ln -sf "$APP/bin/terminal-doom" "$BIN_HOME/terminal-doom"

echo "  installed to $APP"

# --- terminal check ---------------------------------------------------------
# Only terminals that speak the kitty graphics protocol can show the game.
case "${TERM_PROGRAM:-}${TERM:-}" in
  *ghostty*|*kitty*|*WezTerm*|*wezterm*|*cmux*|*vscode*) ;;
  *)
    echo
    echo "  note: this terminal may not support the kitty graphics protocol."
    echo "  ghostty, kitty, WezTerm, cmux and VS Code's terminal all do."
    echo "  macOS:  brew install --cask ghostty"
    ;;
esac

case ":$PATH:" in
  *":$BIN_HOME:"*)
    echo
    echo "  run: terminal-doom"
    ;;
  *)
    echo
    echo "  add $BIN_HOME to your PATH:"
    case "${SHELL:-}" in
      */zsh)  echo "    echo 'export PATH=\"$BIN_HOME:\$PATH\"' >> ~/.zshrc && exec zsh" ;;
      */bash) echo "    echo 'export PATH=\"$BIN_HOME:\$PATH\"' >> ~/.bashrc && exec bash" ;;
      *)      echo "    export PATH=\"$BIN_HOME:\$PATH\"" ;;
    esac
    ;;
esac
