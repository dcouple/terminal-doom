#!/usr/bin/env python3
"""Turn a raw terminal capture into the demo clip.

Puts the captured frames in a mac window on a gradient, captions each key as it
is pressed, and muxes the game's own audio back in. The presentation is added
here; the frames inside the window and the sound are the real recording.

Needs pillow for the overlays, because the ffmpeg most people have on macOS is
built without freetype and so has no drawtext:

    python3 -m venv .venv && .venv/bin/pip install pillow
    .venv/bin/python scripts/polish-demo.py --intro intro.gif --doom doom.mp4 \
        --audio audio.webm --audio-offset 1.94 --out media/terminal-doom.mp4
"""
import argparse
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CANVAS = (1920, 1080)
WIN_W, VIDEO_H, BAR_H = 1440, 858, 46
WIN_H = VIDEO_H + BAR_H
WIN_X, WIN_Y = (CANVAS[0] - WIN_W) // 2, (CANVAS[1] - WIN_H) // 2
RADIUS = 16

PILL_H, PILL_R, PILL_PAD = 96, 28, 46
# The caption straddles the bottom edge of the window, the way a mac hud does.
PILL_Y = WIN_Y + WIN_H - PILL_H // 2

TRAFFIC = ["#ff5f57", "#febc2e", "#28c840"]
FONTS = [
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
]


def font(size):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def gradient(path):
    """A warm-to-cool diagonal wash, in the spirit of a mac desktop.

    Drawn small and scaled up by ffmpeg, which is both quicker and smoother than
    laying down two million pixels one at a time.
    """
    w, h = 320, 180
    stops = [
        (0.00, (0x25, 0x5F, 0xA8)),
        (0.32, (0x4E, 0x9E, 0xD0)),
        (0.54, (0xEB, 0xB9, 0x71)),
        (0.76, (0xE0, 0x86, 0x38)),
        (1.00, (0x84, 0x39, 0x28)),
    ]
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = x / (w - 1) * 0.55 + y / (h - 1) * 0.45
            for k in range(len(stops) - 1):
                t0, c0 = stops[k]
                t1, c1 = stops[k + 1]
                if t <= t1 or k == len(stops) - 2:
                    f = 0.0 if t1 == t0 else min(1.0, max(0.0, (t - t0) / (t1 - t0)))
                    f = f * f * (3 - 2 * f)
                    base = [c0[c] + (c1[c] - c0[c]) * f for c in range(3)]
                    break
            dx, dy = (x / w - 0.5) * 2, (y / h - 0.5) * 2
            shade = 1 - 0.20 * min(1.0, (dx * dx + dy * dy) / 2)
            px[x, y] = tuple(int(v * shade) for v in base)
    img.save(path)


def window_mask(path):
    img = Image.new("L", (WIN_W, WIN_H), 0)
    ImageDraw.Draw(img).rounded_rectangle((0, 0, WIN_W - 1, WIN_H - 1), RADIUS, fill=255)
    img.convert("RGB").save(path)


def titlebar(path, title):
    img = Image.new("RGBA", (WIN_W, BAR_H), (32, 33, 36, 255))
    d = ImageDraw.Draw(img)
    for n, colour in enumerate(TRAFFIC):
        cx, cy, r = 24 + n * 21, BAR_H / 2, 6.5
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour)
    f = font(17)
    d.text((WIN_W / 2, BAR_H / 2), title, font=f, fill="#9aa0a6", anchor="mm")
    img.save(path)


def pill(path, label):
    f = font(46)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    width = int(tmp.textlength(label, font=f)) + PILL_PAD * 2
    img = Image.new("RGBA", (width, PILL_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, PILL_H - 1), PILL_R, fill=(18, 18, 22, 235), outline=(255, 255, 255, 40), width=1)
    d.text((width / 2, PILL_H / 2 - 2), label, font=f, fill="white", anchor="mm")
    img.save(path)
    return width


def shadow(path):
    img = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, WIN_W - 1, WIN_H - 1), RADIUS, fill=(0, 0, 0, 150))
    img.filter(ImageFilter.GaussianBlur(26)).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intro", required=True, help="the shell typing gif from agg")
    ap.add_argument("--doom", required=True, help="the raw terminal capture")
    ap.add_argument("--doom-start", type=float, default=0.0)
    ap.add_argument("--title", default="terminal-doom")
    ap.add_argument("--audio")
    ap.add_argument("--audio-offset", type=float, default=0.0,
                    help="seconds into the doom capture where the audio begins")
    ap.add_argument("--caption", action="append", default=[], metavar="START:END:LABEL",
                    help="times are in the doom capture's own clock")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix="polish-")
    paths = {n: os.path.join(tmp, f"{n}.png") for n in ("bg", "mask", "bar", "shadow")}
    gradient(paths["bg"])
    window_mask(paths["mask"])
    titlebar(paths["bar"], args.title)
    shadow(paths["shadow"])

    captions = []
    for n, spec in enumerate(args.caption):
        start, end, label = spec.split(":", 2)
        path = os.path.join(tmp, f"pill{n}.png")
        captions.append((float(start), float(end), pill(path, label), path))

    intro_len = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         args.intro], capture_output=True, text=True).stdout.strip())
    # Captions are written in the doom capture's clock. On screen they land after
    # the intro, and after whatever was trimmed off the capture's head.
    shift = intro_len - args.doom_start

    inputs = ["-loop", "1", "-i", paths["bg"],
              "-i", args.intro,
              "-ss", str(args.doom_start), "-i", args.doom,
              "-i", paths["bar"], "-i", paths["mask"], "-loop", "1", "-i", paths["shadow"]]
    next_index = 6
    for *_, path in captions:
        inputs += ["-loop", "1", "-i", path]
    audio_index = None
    if args.audio:
        audio_index = next_index + len(captions)
        inputs += ["-i", args.audio]

    graph = [
        f"[0:v]scale={CANVAS[0]}:{CANVAS[1]}:flags=lanczos,fps=20,setsar=1[bg]",
        f"[1:v]scale=-2:{VIDEO_H}:flags=lanczos,pad={WIN_W}:{VIDEO_H}:(ow-iw)/2:0:black,"
        "fps=20,setsar=1[a]",
        f"[2:v]scale={WIN_W}:{VIDEO_H}:flags=lanczos,fps=20,setsar=1[b]",
        "[a][b]concat=n=2:v=1:a=0[screen]",
        "[3:v]fps=20,setsar=1[bar]",
        "[bar][screen]vstack=inputs=2[win]",
        "[4:v]format=gray,fps=20,setsar=1[mask]",
        "[win][mask]alphamerge[winr]",
        "[5:v]fps=20,setsar=1[shadow]",
        f"[bg][shadow]overlay={WIN_X}:{WIN_Y + 20}:shortest=1[bgs]",
        f"[bgs][winr]overlay={WIN_X}:{WIN_Y}[stage]",
    ]

    last = "stage"
    for n, (start, end, width, _) in enumerate(captions):
        a, b = start + shift, end + shift
        x = (CANVAS[0] - width) // 2
        graph.append(
            f"[{last}][{next_index + n}:v]overlay={x}:{PILL_Y}"
            f":enable='between(t\\,{a:.2f}\\,{b:.2f})'[c{n}]"
        )
        last = f"c{n}"

    if audio_index is not None:
        # adelay rather than -itsoffset: the recorder only starts once the game
        # has built its audio graph, some way into the capture, and an input
        # offset gets normalised away again on the way out.
        delay = int((args.audio_offset - args.doom_start + intro_len) * 1000)
        graph.append(f"[{audio_index}:a]adelay={delay}:all=1[aud]")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", *inputs,
           "-filter_complex", ";".join(graph), "-map", f"[{last}]"]
    if audio_index is not None:
        cmd += ["-map", "[aud]", "-c:a", "aac", "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "slow", "-crf", "20",
            "-movflags", "+faststart", "-shortest", args.out]

    subprocess.run(cmd, check=True)
    print(f"{args.out}: intro {intro_len:.2f}s, captions shifted {shift:+.2f}s",
          file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
