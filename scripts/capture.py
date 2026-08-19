#!/usr/bin/env python3
"""Play terminal-doom inside a pretend terminal and record what it paints.

terminal-browser draws by writing kitty graphics escape sequences to its
terminal, and reads the player's keys back off the same pipe. So a program
holding the other end of a pty can be the terminal: answer the capability
queries, keep the frames that arrive, and type into the game.

That makes it possible to prove the whole thing works — boots, renders, takes
input — on a machine with no display, and to record the result without a screen
recorder.

    scripts/capture.py --out media --video demo.mp4 --seconds 30 \
        --still 6:title --key 8:enter -- bin/terminal-doom

Frames arrive as f=32 (RGBA) transfers pointing at a temp file, which is what
terminal-browser uses on macOS and Linux for speed.
"""
import argparse
import base64
import fcntl
import os
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import time
import zlib

ESC = b"\x1b"

# kitty keyboard protocol: CSI number ; modifiers : event-type u, and for keys
# that have a legacy escape code, CSI 1 ; modifiers : event-type <final>.
PRESS, RELEASE = 1, 3
LEGACY = {"up": b"A", "down": b"B", "right": b"C", "left": b"D"}
UNICODE = {
    "enter": 13, "return": 13, "esc": 27, "escape": 27, "space": 32,
    "tab": 9, "backspace": 127,
}
# Modifiers are functional keys in the protocol, and a real terminal reports the
# modifier as held in the same event that presses it.
MODIFIERS = {"ctrl": (57442, 5), "shift": (57441, 2), "alt": (57443, 3)}


def key_event(name, event):
    name = name.lower()
    if name in MODIFIERS:
        code, mods = MODIFIERS[name]
        return b"%s[%d;%d:%du" % (ESC, code, mods, event)
    if name in LEGACY:
        return b"%s[1;1:%d%s" % (ESC, event, LEGACY[name])
    code = UNICODE.get(name)
    if code is None:
        if len(name) != 1:
            raise SystemExit(f"capture: don't know the key {name!r}")
        code = ord(name)
    return b"%s[%d;1:%du" % (ESC, code, event)


def write_png(path, width, height, rgba):
    """A PNG writer, so the harness needs nothing but the standard library."""
    raw = b"".join(
        b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height)
    )

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


class FakeTerminal:
    """Enough of a terminal for terminal-browser to believe in it."""

    def __init__(self, cols, rows, cell_w, cell_h):
        self.cols, self.rows = cols, rows
        self.cell_w, self.cell_h = cell_w, cell_h
        self.width, self.height = cols * cell_w, rows * cell_h
        self.kbd_stack = [0]
        self.frame = None          # most recent RGBA bytes
        self.frame_size = None     # (w, h)
        self.frames_seen = 0
        self.pid = self.fd = None
        self.textlog = None

    def spawn(self, argv):
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-kitty"
            os.environ["COLORTERM"] = "truecolor"
            os.environ["TERM_PROGRAM"] = "ghostty"
            os.execvp(argv[0], argv)
        self.pid, self.fd = pid, fd
        # ws_xpixel/ws_ypixel is where terminal-browser reads the pane size from,
        # so the frames come back at exactly this resolution.
        fcntl.ioctl(fd, termios.TIOCSWINSZ,
                    struct.pack("HHHH", self.rows, self.cols, self.width, self.height))
        return self

    # -- the terminal side of the conversation ------------------------------
    def answer(self, chunk):
        out = b""

        for m in re.finditer(rb"\x1b_G([^;\x1b]*);?([^\x1b]*)\x1b\\", chunk):
            ctrl, payload = m.group(1), m.group(2)
            fields = dict(
                kv.split(b"=", 1) for kv in ctrl.split(b",") if b"=" in kv
            )
            if fields.get(b"a") == b"q":
                out += ESC + b"_Gi=" + fields.get(b"i", b"0") + b";OK" + ESC + b"\\"
            elif fields.get(b"a") == b"T":
                self._take_frame(fields, payload)

        for m in re.finditer(rb"\x1b\[(>?)c", chunk):
            out += ESC + (b"[>1;4000;0c" if m.group(1) else b"[?62;4;22c")

        # kitty keyboard protocol: track the push/pop stack so the query can be
        # answered with the flags actually in force. Answering at all is what
        # tells terminal-browser it may send key releases, which a game needs.
        for m in re.finditer(rb"\x1b\[([><])(\d*)u", chunk):
            if m.group(1) == b">":
                self.kbd_stack.append(int(m.group(2) or 0))
            elif len(self.kbd_stack) > 1:
                self.kbd_stack.pop()
        if re.search(rb"\x1b\[\?u", chunk):
            out += b"%s[?%du" % (ESC, self.kbd_stack[-1])

        if re.search(rb"\x1b\[14t", chunk):
            out += b"%s[4;%d;%dt" % (ESC, self.height, self.width)
        if re.search(rb"\x1b\[16t", chunk):
            out += b"%s[6;%d;%dt" % (ESC, self.cell_h, self.cell_w)
        if re.search(rb"\x1b\[18t", chunk):
            out += b"%s[8;%d;%dt" % (ESC, self.rows, self.cols)

        for m in re.finditer(rb"\x1b\[\?(\d+)\$p", chunk):
            out += b"%s[?%s;2$y" % (ESC, m.group(1))

        for m in re.finditer(rb"\x1b\](1[01]);\?(?:\x1b\\|\x07)", chunk):
            which = m.group(1)
            rgb = b"0000/0000/0000" if which == b"11" else b"ffff/ffff/ffff"
            out += ESC + b"]" + which + b";rgb:" + rgb + ESC + b"\\"
        for m in re.finditer(rb"\x1b\]4;(\d+);\?(?:\x1b\\|\x07)", chunk):
            out += ESC + b"]4;" + m.group(1) + b";rgb:8080/8080/8080" + ESC + b"\\"

        for m in re.finditer(rb"\x1bP\+q([0-9a-fA-F;]*)\x1b\\", chunk):
            out += ESC + b"P0+r" + m.group(1) + ESC + b"\\"

        return out

    def _take_frame(self, fields, payload):
        if fields.get(b"t") != b"f" or fields.get(b"f") != b"32":
            return
        try:
            w, h = int(fields[b"s"]), int(fields[b"v"])
            path = base64.b64decode(payload).decode()
            with open(path, "rb") as fh:
                data = fh.read(w * h * 4)
        except (KeyError, ValueError, OSError):
            return
        if len(data) == w * h * 4:
            self.frame, self.frame_size = data, (w, h)
            self.frames_seen += 1

    def send(self, data):
        os.write(self.fd, data)

    def pump(self, timeout=0.02):
        r, _, _ = select.select([self.fd], [], [], timeout)
        if self.fd not in r:
            return True
        try:
            chunk = os.read(self.fd, 1 << 22)
        except OSError:
            return False
        if not chunk:
            return False
        if self.textlog:
            # keep the readable half of the stream: everything but the frames
            self.textlog.write(re.sub(rb"\x1b_G[^\x1b]*\x1b\\\\", b"", chunk))
            self.textlog.flush()
        reply = self.answer(chunk)
        if reply:
            os.write(self.fd, reply)
        return True

    def close(self):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(self.pid), sig)
            except (ProcessLookupError, PermissionError):
                try:
                    os.kill(self.pid, sig)
                except ProcessLookupError:
                    break
            time.sleep(0.4)
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            pass


def parse_timed(values, parts):
    out = []
    for v in values or []:
        bits = v.split(":", parts - 1)
        if len(bits) != parts:
            raise SystemExit(f"capture: expected {parts} colon-separated fields in {v!r}")
        out.append((float(bits[0]), *bits[1:]))
    return sorted(out, key=lambda item: item[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="media", help="directory for stills and video")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--cols", type=int, default=170)
    ap.add_argument("--rows", type=int, default=48)
    ap.add_argument("--cell", default="9x19", help="cell size in pixels, WxH")
    ap.add_argument("--video", help="filename for an mp4 of the whole run")
    ap.add_argument("--gif", help="filename for a gif of the whole run")
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--still", action="append", metavar="TIME:NAME")
    ap.add_argument("--key", action="append", metavar="TIME:KEY",
                    help="tap a key, e.g. 8:enter")
    ap.add_argument("--hold", action="append", metavar="TIME:SECONDS:KEY",
                    help="hold a key down, e.g. 12:1.5:w")
    ap.add_argument("--log", help="write the child's non-graphics output here")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    argv = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not argv:
        raise SystemExit("capture: give the command to run after --")

    cell_w, cell_h = (int(n) for n in args.cell.lower().split("x"))
    os.makedirs(args.out, exist_ok=True)

    stills = parse_timed(args.still, 2)
    taps = parse_timed(args.key, 2)
    holds = parse_timed(args.hold, 3)
    # A hold is a press now and a release later; flatten both into one timeline.
    events = [(t, key_event(k, PRESS)) for t, k in taps]
    events += [(t + 0.06, key_event(k, RELEASE)) for t, k in taps]
    for t, dur, k in holds:
        events.append((t, key_event(k, PRESS)))
        events.append((t + float(dur), key_event(k, RELEASE)))
    events.sort(key=lambda e: e[0])

    term = FakeTerminal(args.cols, args.rows, cell_w, cell_h)
    if args.log:
        term.textlog = open(args.log, "wb")
    term.spawn(argv)

    encoder = None
    frame_interval = 1.0 / args.fps
    next_frame = frame_interval
    written = 0

    start = time.time()
    # Capture mode writes the game's audio out separately; this is the clock the
    # two get lined up against.
    with open(os.path.join(args.out, "capture-start"), "w") as fh:
        fh.write(str(start))
    try:
        while (now := time.time() - start) < args.seconds:
            while events and events[0][0] <= now:
                term.send(events.pop(0)[1])
            while stills and stills[0][0] <= now:
                _, name = stills.pop(0)
                if term.frame:
                    w, h = term.frame_size
                    write_png(os.path.join(args.out, f"{name}.png"), w, h, term.frame)
                    print(f"still {name}.png at {now:.1f}s ({w}x{h})", file=sys.stderr)
                else:
                    print(f"still {name} skipped, nothing painted yet", file=sys.stderr)

            if (args.video or args.gif) and now >= next_frame and term.frame:
                if encoder is None:
                    w, h = term.frame_size
                    encoder = subprocess.Popen(
                        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                         "-f", "rawvideo", "-pix_fmt", "rgba",
                         "-s", f"{w}x{h}", "-r", str(args.fps), "-i", "-",
                         "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                         "-preset", "veryfast", "-crf", "20",
                         os.path.join(args.out, args.video or "capture.mp4")],
                        stdin=subprocess.PIPE)
                encoder.stdin.write(term.frame)
                written += 1
                next_frame += frame_interval

            if not term.pump():
                break
    finally:
        if encoder:
            encoder.stdin.close()
            encoder.wait()
        term.close()

    print(f"painted {term.frames_seen} frames, encoded {written}", file=sys.stderr)
    if term.frames_seen == 0:
        print("capture: nothing was ever painted", file=sys.stderr)
        return 1

    if args.gif and args.video:
        src = os.path.join(args.out, args.video)
        dst = os.path.join(args.out, args.gif)
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
             "-vf", "fps=14,scale=900:-1:flags=lanczos,split[a][b];"
                    "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer",
             dst], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
