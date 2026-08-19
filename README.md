# terminal-doom

DOOM, running inside your terminal.

![terminal-doom running in a terminal pane](media/terminal-doom.gif)

Not ASCII art, and not a screenshot — those are real pixels, drawn into a
terminal pane through the [kitty graphics protocol][kgp], taking your keyboard
the whole time.

### Install (macOS & Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/dcouple/terminal-doom/main/install.sh | bash
```

That pulls in [terminal-browser][tb] if you do not have it, and puts
`terminal-doom` on your PATH. The game itself ships with it — the wasm and the
shareware wad are in the repo, so it works on a plane.

### Play

```bash
terminal-doom                # take over this pane
terminal-doom --split right  # play beside whatever you were doing
```

You need a terminal that speaks the kitty graphics protocol: **ghostty**,
**kitty**, **WezTerm**, **cmux**, or VS Code's built-in terminal. On macOS,
`brew install --cask ghostty`.

| | |
| --- | --- |
| Move | `W` `A` `S` `D` |
| Turn | arrow keys, or the mouse |
| Fire | `ctrl` |
| Open doors, use switches | `space` |
| Weapons | `1` – `7` |
| Menu | `esc` |
| Quit the pane | `ctrl+q` |

Leave it alone on the title screen and DOOM plays its own attract-mode demos,
the same recorded playbacks id shipped in the wad in 1993.

**Make it look good.** Fullscreen the terminal first — `cmd+enter` in ghostty,
`ctrl+shift+enter` on Linux. The game is 320×200 upscaled with nearest-neighbour
to whatever the pane is, so a bigger pane is a bigger, sharper DOOM, and a
fullscreen 4K pane looks startlingly good. There is no toolbar, no border and no
cursor: the pane is only the game.

```
terminal-doom --split right --size 0.5   # half the screen, agent in the other half
terminal-doom --serve                    # just the game server, print its url
```

### How it works

Three pieces:

- **[Chocolate Doom][cd]** — the conservative, source-accurate DOOM port —
  compiled to WebAssembly via [cloudflare/doom-wasm][cfd].
- A **static server on loopback**, because wasm cannot be loaded over `file://`.
  It picks an ephemeral port and dies with the game.
- **[terminal-browser][tb]**, which runs chromium offscreen and pushes its frames
  into the terminal as kitty graphics, then feeds terminal key events back to the
  page as synthetic browser events.

So the stack is: DOOM → wasm → chromium → escape codes → your terminal. Every
frame you see took that route, at 35 tics a second.

It works over **ssh** for the same reason terminal-browser does: the frames are
just bytes on the wire. DOOM on a box in another country, rendered in the
terminal on your desk.

### Building the engine

The committed `web/doom.js` and `web/doom.wasm` are enough to play. To rebuild
them:

```bash
brew install automake pkgconf     # linux: apt install automake pkgconf
scripts/build-wasm.sh
```

It clones [cloudflare/doom-wasm][cfd] at a pinned commit, fetches a pinned
emscripten (3.1.64), applies `scripts/patch-doom-wasm.py`, and drops the result
into `web/`. The exact commit and toolchain of the shipped binaries are recorded
in `web/BUILD-INFO`.

Three things the port needed before it would boot at all, all of them recorded
in that patch script:

1. **`boolean` has to stay four bytes wide.** `doomtype.h` declares its own
   `enum { false, true } boolean`, which stopped compiling once SDL2 started
   pulling in `<stdbool.h>`. The header's own fallback is `typedef bool
   boolean` — and that one is quietly fatal. DOOM `memset`s whole sprite tables
   to `-1` and later tests them against `true`, which is well defined for a four
   byte enum and undefined for a one byte `_Bool`. Read back through a `_Bool`
   the `-1` sentinel comes out true, and the boot dies in `r_things.c` with
   *"Sprite TROO frame I has rotations and a rot=0 lump"* — an error that looks
   exactly like a corrupt wad and is not.
2. **`-nomusic`.** The port's OPL emulation never finishes initialising under
   emscripten and hangs before the game window ever appears. Sound effects are
   unaffected, and upstream ships the same flag for the same reason.
3. **`force_software_renderer`.** SDL's webgl path renders into a context whose
   pixels terminal-browser cannot read back; the canvas-2d path composites
   normally. DOOM is 320×200, so the software renderer costs nothing.

### Proving it works without a screen

`scripts/capture.py` pretends to be a ghostty-class terminal. It puts the game
on a pty, answers the kitty graphics and keyboard handshakes, decodes the RGBA
frames terminal-browser transmits, and can type into the game — so the whole
thing can be tested, screenshotted and recorded on a machine with no display
attached. The gif at the top of this file was made with it.

```bash
scripts/capture.py --out media --video demo.mp4 --seconds 32 \
  --key 4:enter --key 6:enter --hold 12:3.0:w --key 19:ctrl \
  --still 13:play -- bin/terminal-doom
```

`--key` taps, `--hold` holds a key down for a duration (which is what movement
needs), `--still` writes a png at a moment, `--video` records the run. It is a
genuine end-to-end check: if a frame comes back with DOOM in it, then the wasm
booted, chromium rendered, the escape codes were well formed and the keys
arrived.

The harness decodes frames but draws no text, so it cannot show the shell you
type the command into. `scripts/record-intro.py` records that half separately —
a real shell on a real pty, typed into at human speed, written out as an
asciicast that [agg][agg] renders. The demo above is those two real recordings
cut together at the moment the command runs.

### What it does not do

- **No music.** See above. Sound effects work.
- **Shareware only, out of the box.** The included wad is the freely
  distributable first episode, Knee-Deep in the Dead. If you own the full game,
  point it at your own iwad by dropping it in as `web/doom1.wad`.
- **No Windows build.** The kitty graphics protocol is thin on the ground there.
  WSL works.
- **Save games do not persist** across runs; the emscripten filesystem is
  in-memory.

### Licence

Three parts, three licences — see [NOTICE](NOTICE):

- the wrapper (`bin/`, `scripts/`, `web/index.html`, `web/serve.mjs`) is **MIT**
- the engine (`web/doom.js`, `web/doom.wasm`) is **GPLv2**, from Chocolate Doom
- the game data (`web/doom1.wad`) is **id Software shareware**, included
  unmodified

DOOM is a trademark of id Software LLC. This project is not affiliated with id
Software, ZeniMax or Bethesda.

### Thanks

- [zenbu-labs/terminal-browser][tb], which does the genuinely hard part
- [terminal-code][tc], which showed that a web app in a terminal pane can be a
  real product
- [cloudflare/doom-wasm][cfd] and [Chocolate Doom][cd]
- id Software, for shipping the source

[agg]: https://docs.asciinema.org/manual/agg/
[kgp]: https://sw.kovidgoyal.net/kitty/graphics-protocol/
[tb]: https://github.com/zenbu-labs/terminal-browser
[tc]: https://github.com/zenbu-labs/terminal-code
[cd]: https://github.com/chocolate-doom/chocolate-doom
[cfd]: https://github.com/cloudflare/doom-wasm
