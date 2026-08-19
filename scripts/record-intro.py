#!/usr/bin/env python3
"""Record a real shell session typing the terminal-doom command, as an asciicast.

The capture harness can decode the frames terminal-browser paints, but it is not
a terminal emulator — it draws no text. So the first seconds of the demo, the
part where a person types the command, are recorded here instead: a real shell
on a real pty, typed into at human speed, written out as an asciicast that agg
renders to video. The two halves are then cut together.

    scripts/record-intro.py /tmp/intro.cast
    agg /tmp/intro.cast /tmp/intro.gif --font-size 26
"""
import json
import os
import pty
import select
import sys
import termios
import struct
import fcntl
import time

COLS, ROWS = 92, 24
COMMAND = "terminal-doom"
# Typing is not metronomic. These are per-character delays in seconds, cycled,
# so the line lands somewhere near a real 90 words per minute.
RHYTHM = [0.075, 0.052, 0.11, 0.064, 0.048, 0.092, 0.058, 0.13, 0.07, 0.05]


def main(out_path):
    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.environ["PS1"] = ""
        # -f skips the user's rc files, so the recording does not depend on
        # whatever this particular machine has in .zshrc.
        os.execvp("zsh", ["zsh", "-f"])

    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    events = []
    start = time.time()

    def drain(until):
        while time.time() < until:
            r, _, _ = select.select([fd], [], [], 0.01)
            if fd not in r:
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:
                return False
            if not data:
                return False
            events.append([round(time.time() - start, 4), "o",
                           data.decode("utf-8", "replace")])
        return True

    # A clean prompt: no path, no hostname, nothing to identify a machine.
    # zsh -f starts with a bare PATH, so put the install dir back before the
    # recording begins — the setup line is trimmed off below either way.
    os.write(fd, b"export PATH=\"$HOME/.local/bin:$PATH\"; "
                 b"PROMPT='%F{240}~%f %F{35}\xe2\x9d\xaf%f '; clear\n")
    drain(time.time() + 1.2)
    # Everything up to the screen clear is this setup, so start the recording at
    # the clear itself: the replay then opens on a blank screen and a prompt.
    for i in reversed(range(len(events))):
        if "\x1b[2J" in events[i][2] or "\x1b[H" in events[i][2]:
            offset = events[i][0]
            del events[:i]
            for event in events:
                event[0] = round(event[0] - offset, 4)
            break
    else:
        sys.exit("record-intro: the shell never cleared the screen")
    start = time.time() - events[-1][0]
    drain(time.time() + 0.7)

    for i, ch in enumerate(COMMAND):
        os.write(fd, ch.encode())
        drain(time.time() + RHYTHM[i % len(RHYTHM)])

    drain(time.time() + 0.45)   # the beat before hitting return
    os.write(fd, b"\r")
    drain(time.time() + 0.5)

    try:
        os.kill(pid, 9)
        os.waitpid(pid, os.WNOHANG)
    except (ProcessLookupError, ChildProcessError):
        pass

    header = {
        "version": 2, "width": COLS, "height": ROWS,
        "env": {"TERM": "xterm-256color", "SHELL": "/bin/zsh"},
    }
    with open(out_path, "w") as fh:
        fh.write(json.dumps(header) + "\n")
        for event in events:
            fh.write(json.dumps(event) + "\n")
    print(f"{out_path}: {len(events)} events, {events[-1][0]:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "intro.cast")
