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

### How this was made

Two agents made this, each doing the job it is good at. I run my work inside
[Pane](https://github.com/dcouple/Pane), a workspace that gives every task its
own git worktree and agent terminal. A chat orchestrator sits above the agents,
a Claude Fable 5 session running the pane-orchestrator skill from
[dcouple/skills](https://github.com/dcouple/skills) with the workflow
conventions from [dcouple/orchestra](https://github.com/dcouple/orchestra). It
writes the briefs, dispatches the work, and carries my messages to agents while
they run.

I sent the orchestrator the
[terminal-code](https://github.com/zenbu-labs/terminal-code) tweet and asked
for DOOM the same way. This is the raw message, typos and all:

```
i saw a tweet go viral where someone got vs code running in a terminal (since
its just web/opens ource) and im wondering if we can do the same thing but get
doom running in a terminal using
https://github.com/zenbu-labs/terminal-browser#how-does-it-work (which is what
he used) i mainly wnat it to go viral lol
```

It created a worktree, wrote a one-page brief, and
handed it to a Claude Opus 5 agent. The brief set the ground rules: read
terminal-browser and terminal-code first, pick an existing web DOOM, ship the
shareware wad only, self-host everything so the install one-liner keeps working
on its own, prove that keys reach the game, and finish with a recording and the
steps to reproduce it. Everything else was the agent's to figure out: which
port, how to build it, what broke and why, and how to license a project whose
engine is GPL and whose data is shareware. It figured those out and reported
back. First command to public repo took 53 minutes, and the recording took
about another hour after I asked for polish.

The brief is in [BRIEF.md](BRIEF.md), verbatim, along with the one message the
orchestrator relayed mid-build. If you want to see what the delegation actually
looked like, that file is the whole of it.

The part I did not expect: the machine it was working on has screen recording
switched off, so it could not see the terminal it was driving. Instead of asking
me to turn it on, it wrote a terminal. `scripts/capture.py` holds the far end of
a pty, answers the queries a real terminal answers, decodes the frames
terminal-browser transmits, and types back in the kitty keyboard encoding, held
keys and modifiers included, because a game needs key releases and a tap is not
a walk.

That one file ended up doing three jobs. It was the debugger, since every "is
this working" question became a png. It was the test suite, because a frame with
DOOM in it means the wasm booted, chromium rendered, the escape codes were well
formed and the keys arrived. And it was the camera: every frame in the recording
above is bytes terminal-browser actually wrote to a terminal, which is why the
ammo counter really does tick down as `ctrl` is pressed.

It found the boot bug the same way. DOOM was dying with a sprite error that
reads exactly like a corrupt wad, so it went and fetched the canonical shareware
wad, hash-verified it, watched the error survive, and then found the real cause
in a patch it had written itself twenty minutes earlier. That is the `_Bool`
story below.

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

`scripts/capture.py`, from the story above, is a normal way to test this thing:

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
- [Pane](https://github.com/dcouple/Pane), [dcouple/skills](https://github.com/dcouple/skills) and [dcouple/orchestra](https://github.com/dcouple/orchestra), the workspace and orchestration this was built inside
- [terminal-code](https://github.com/zenbu-labs/terminal-code), which showed a web app in a terminal pane can be a real product
- [cloudflare/doom-wasm](https://github.com/cloudflare/doom-wasm) and [Chocolate Doom](https://github.com/chocolate-doom/chocolate-doom)
- id Software, for shipping the source
