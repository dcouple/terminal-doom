# The brief, verbatim

This is the exact brief the orchestrator wrote and delegated to the build agent,
unedited. Two mid-flight messages follow it.

---

You own a viral experiment: DOOM running inside a terminal, in the style of the viral "VS Code in the terminal" project. Goal is a shippable, tweetable artifact — mainly: it must look incredible in a clip and be reproducible by strangers with one command.

Reference implementations to study FIRST (clone both into refs/):
- https://github.com/zenbu-labs/terminal-browser — a real Chromium browser rendered into the terminal via the kitty graphics protocol. Has `terminal-browser open <url>`, split panes, an agent-compatible `action` CLI, and built-in page recording.
- https://github.com/zenbu-labs/terminal-code — how they wrapped VS Code (code-server-style web build) into a polished terminal product on top of the same rendering. This is the pattern: web app + launcher CLI + terminal rendering. Study its src/ + web/ layout, install script, and how it manages the browser process.

The work, in order:
1. Install terminal-browser (curl installer in its README) and confirm what it needs (kitty graphics protocol: ghostty, kitty, etc. — brew install ghostty or kitty if none present). Note: YOUR terminal here may not support kitty graphics, so verify rendering by driving it from outside — `terminal-browser action` screenshots/recordings — rather than by eyeballing.
2. Find the best web DOOM to embed. Candidates to evaluate: js-dos DOOM (dos.zone), a WebAssembly chocolate-doom/Crispy Doom port, or any wasm DOOM that (a) boots straight into the game with zero clicks or minimal automatable clicks, (b) takes keyboard input reliably, (c) uses the legally redistributable shareware DOOM1.WAD only. Prefer one we can self-host as static files in this repo (offline, no third-party uptime risk) — that also makes the one-liner durable.
3. Cheapest viable product first: `doom` script that launches `terminal-browser open <local file or localhost url>` fullscreen, keys reaching the game. Verify input actually reaches DOOM via the action CLI (send keys, screenshot, confirm the menu moved).
4. If the cheap path works, polish toward the terminal-code pattern: a `terminal-doom` wrapper CLI (open, --split, sensible zoom), an install one-liner script, README with the clip embedded.
5. Produce the artifacts: short recording (terminal-browser's built-in recording or asciinema+screen capture of ghostty) showing boot → menu → a few seconds of gameplay; a README; a draft tweet (one line + the one-liner command). parsa will record the hero gameplay clip himself — your recording proves it works and shows him the setup.

Work in this repo (parsakhaz/experiments) under terminal-doom/. Commit as you go.
Hard stops: no publishing anywhere (no npm, no releases, no posting) — repo commits and an open PR only, then stop. End your report with assumptions made, plus exact steps for parsa to run it in ghostty and record.

---

## Mid-flight message 1

> Note for your step-5 tweet draft (build first, this is for later): parsa wants it to mirror the terminal-code announcement format exactly — 'Introducing terminal-doom: DOOM inside the terminal' followed by three short dash bullets (pick the three strongest true ones, e.g. one-command install, works over ssh, plays with your keyboard) and a link line. Then a second line crediting the inspiration: 'Inspired by @RobKnight__'s VS Code in the terminal'. The tweet ships with a screen recording of live gameplay in the terminal, so make sure your handoff steps for parsa produce a clean recordable run (ghostty fullscreen, no debug noise on screen). Keep building; fold this into the final report.

## About the orchestration

The orchestrator is a chat session of Claude Fable 5 running the
pane-orchestrator skill. It manages work through
[Pane](https://github.com/dcouple/Pane), which gives every task its own git
worktree and agent terminal. The skills and workflow conventions it follows
live in [dcouple/skills](https://github.com/dcouple/skills) and
[dcouple/orchestra](https://github.com/dcouple/orchestra).
