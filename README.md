# terminal-doom

DOOM inside your terminal

![terminal-doom](media/terminal-doom.gif)

### Install (macOS & Linux):

```bash
curl -fsSL https://raw.githubusercontent.com/dcouple/terminal-doom/main/install.sh | bash
```

The game comes with it. There is no wad to go and find.

### Usage

```
Usage: terminal-doom [options]

  terminal-doom                 Play DOOM in this terminal pane
  terminal-doom --split right   Play in a new pane beside what you are doing

Options:
  --split <direction>   Open in a new pane: right, left, down, up
  --size <fraction>     How much space a new split takes (0.2 to 0.95)
  --port <n>            Serve the game on a fixed port
  --serve               Only start the server and print its url
  --windowed            Keep the browser toolbar, for debugging
  --version             Print the version
  -h, --help            Print this help
```

You need a terminal that speaks the kitty graphics protocol: ghostty, kitty,
WezTerm, cmux, or the terminal inside VS Code. On macOS, `brew install --cask
ghostty`.

Fullscreen the terminal before you play. The game is 320x200 upscaled to
whatever the pane is, so a bigger pane is a bigger, sharper DOOM.

### Controls

| Action | Key |
| --- | --- |
| Move | `W` `A` `S` `D` |
| Turn | arrow keys, or the mouse |
| Fire | `ctrl` |
| Open doors and switches | `space` |
| Weapons | `1` to `7` |
| Menu | `esc` |
| Quit the pane | `ctrl+q` |

Leave it alone at the title screen and DOOM plays the attract demos id shipped
in the wad in 1993.

Two things to know before you get attached to a run. There is no music, because
the port's OPL emulation hangs under emscripten; sound effects work. And saved
games do not survive quitting, because the game's filesystem lives in memory.

What ships is the shareware episode, Knee-Deep in the Dead. If you own the full
game, drop your own iwad in as `web/doom1.wad`.

### How does it work?

terminal-doom combines [terminal-browser](https://github.com/zenbu-labs/terminal-browser)
(a browser in the terminal) and [doom-wasm](https://github.com/cloudflare/doom-wasm)
(Chocolate Doom compiled to WebAssembly). A small server on loopback hands the
game to the browser, because wasm cannot load over `file://`.

So the frames go DOOM, wasm, chromium, escape codes, your terminal, 35 times a
second. Your keys make the same trip back. It works over ssh for the same reason
terminal-browser does: the frames are only bytes on the wire.

Three things the port needed before it would boot:

- `boolean` has to stay four bytes wide. `doomtype.h` declares its own
  `enum { false, true }`, which stopped compiling once SDL2 started including
  `<stdbool.h>`. Its fallback, `typedef bool boolean`, is quietly fatal: DOOM
  memsets sprite tables to `-1` and tests them against `true`, which is defined
  for a four byte enum and not for a one byte `_Bool`. Read through a `_Bool` the
  sentinel comes back true, and the boot dies in `r_things.c` complaining about a
  sprite, which looks exactly like a corrupt wad.
- `-nomusic`, for the reason above.
- `force_software_renderer`, so the game draws through canvas 2d, whose pixels
  terminal-browser can read back.

`scripts/build-wasm.sh` rebuilds the engine from a pinned commit with a pinned
emscripten and applies those patches. You do not need it to play.

### Testing it without a screen

`scripts/capture.py` pretends to be a terminal. It puts the game on a pty,
answers the kitty graphics and keyboard handshakes, decodes the frames coming
back, and types into the game. That makes the whole chain testable on a machine
with no display, and it is how the recording above was made.

```bash
scripts/capture.py --out media --video demo.mp4 --seconds 16 \
  --key 4.5:enter --hold 9.4:2.1:w --key 11.6:ctrl -- bin/terminal-doom
```

### Windows

The kitty graphics protocol is thin on the ground on Windows, and there is no
Windows build. Installing the Linux version inside
[WSL](https://learn.microsoft.com/en-us/windows/wsl/install) works.

### Licence

Three parts, three licences, spelled out in [NOTICE](NOTICE). The wrapper is
MIT. The engine is GPLv2, from Chocolate Doom. The wad is id Software shareware,
included unmodified. DOOM is a trademark of id Software LLC, who are not
involved in this.

### Thanks

- [terminal-browser](https://github.com/zenbu-labs/terminal-browser), which does the hard part
- [terminal-code](https://github.com/zenbu-labs/terminal-code), which showed a web app in a terminal pane can be a real product
- [cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm) and [Chocolate Doom](https://github.com/chocolate-doom/chocolate-doom)
- id Software, for shipping the source
