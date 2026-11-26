"""Render the live demo's real terminal output into demo/watchdog_demo.mp4 and .gif.

    python demo/make_video.py

Runs demo/live_demo.py, captures its colored output, and draws it as a
terminal recording: one scene per screen, lines appearing in order, with a
title card and a results card. Needs Pillow and ffmpeg.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 720
PAD_X, TOP = 36, 64
def _first_font(*paths: str) -> str:
    for p in paths:
        if Path(p).exists():
            return p
    raise SystemExit("No monospace font found; set FONT_PATH in demo/make_video.py")


FONT_PATH = _first_font("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",   # Linux
                        "/System/Library/Fonts/Menlo.ttc",                         # macOS
                        "C:/Windows/Fonts/consola.ttf")                            # Windows
BOLD_PATH = _first_font("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                        "/System/Library/Fonts/Menlo.ttc", "C:/Windows/Fonts/consolab.ttf")
SIZE, LINE_H = 17, 25
BG, BAR, FG, DIMC = (15, 17, 21), (30, 33, 41), (230, 232, 238), (120, 128, 145)
COLORS = {"31": (255, 93, 93), "32": (76, 208, 138), "33": (245, 185, 66), "36": (79, 195, 217)}

font = ImageFont.truetype(FONT_PATH, SIZE)
bold = ImageFont.truetype(BOLD_PATH, SIZE)
CHAR_W = font.getlength("M")
COLS = int((W - 2 * PAD_X) // CHAR_W)
ROWS = (H - TOP - 20) // LINE_H
ANSI = re.compile(r"\x1b\[([\d;]*)m")


def spans(line: str):
    """Yield (text, color, is_bold) from an ANSI line."""
    color, is_bold, pos = FG, False, 0
    for m in ANSI.finditer(line):
        if m.start() > pos:
            yield line[pos:m.start()], color, is_bold
        codes = m.group(1).split(";") if m.group(1) else ["0"]
        for code in codes:
            if code == "0":
                color, is_bold = FG, False
            elif code == "1":
                is_bold = True
            elif code == "2":
                color = DIMC
            elif code in COLORS:
                color = COLORS[code]
        pos = m.end()
    if pos < len(line):
        yield line[pos:], color, is_bold


def wrap(line: str) -> list[str]:
    """Wrap an ANSI line to the terminal width, carrying the active color onto continuation lines."""
    plain_len = len(ANSI.sub("", line))
    if plain_len <= COLS:
        return [line]
    parts = list(spans(line))
    out, cur, n = [], [], 0
    indent = len(ANSI.sub("", line)) - len(ANSI.sub("", line).lstrip()) + 2
    for text, color, b in parts:
        for word in re.split(r"(\s+)", text):
            if n + len(word) > COLS and n > indent:
                out.append(cur)
                cur, n = [(" " * indent, FG, False)], indent
                word = word.lstrip()
            cur.append((word, color, b))
            n += len(word)
    out.append(cur)
    return out


def frame(lines: list, title: str = "mcp-watchdog — live demo") -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 40], fill=BAR)
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([18 + i * 22, 14, 30 + i * 22, 26], fill=col)
    d.text((W / 2, 20), title, font=font, fill=DIMC, anchor="mm")
    y = TOP
    for ln in lines[-ROWS:]:
        x = PAD_X
        segs = list(spans(ln)) if isinstance(ln, str) else ln
        for text, color, b in segs:
            d.text((x, y), text, font=bold if b else font, fill=color)
            x += CHAR_W * len(text)
        y += LINE_H
    return img


def card(big: str, small: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_big = ImageFont.truetype(BOLD_PATH, 40)
    d.text((W / 2, H / 2 - 40 - 18 * len(small)), big, font=f_big, fill=FG, anchor="mm")
    for i, s in enumerate(small):
        d.text((W / 2, H / 2 + 10 + i * 34 - 18 * len(small) + 20), s, font=ImageFont.truetype(FONT_PATH, 22),
               fill=COLORS["36"] if i == 0 else FG, anchor="mm")
    return img


def main() -> None:
    env = {**os.environ, "FORCE_COLOR": "1"}
    out = subprocess.run([sys.executable, str(ROOT / "demo" / "live_demo.py")], capture_output=True, text=True,
                         env=env, check=True, timeout=120).stdout.splitlines()

    held = json.loads((ROOT / "bench" / "results" / "v1" / "heldout.json").read_text())
    p, q = held["priority"], held["queue"]

    shots: list[tuple[Image.Image, float]] = []
    shots.append((card("MCP Watchdog", ["Is the tool my agent is about to call", "still the one I approved?"]), 4.0))

    screen: list = []
    for raw in out:
        plain = ANSI.sub("", raw)
        if plain.startswith("▶"):
            if screen:
                shots.append((frame(screen), 2.2))
            screen = []
            for w in wrap(raw):
                screen.append(w)
            shots.append((frame(screen), 1.4))
            continue
        for w in wrap(raw):
            screen.append(w)
            hold = 0.25
            if "PAUSED" in plain or "sent" in plain.split()[:1]:
                hold = 1.1
            if "why:" in plain:
                hold = 1.6
            if "No review needed" in plain:
                hold = 1.2
            shots.append((frame(screen), hold))
    shots.append((frame(screen), 3.0))
    shots.append((card("v1 held-out benchmark (22 unseen cases)", [
        f"Sensitive changes ranked high: {p['high_ranked_high']} of {p['n_high']}",
        f"Routine changes wrongly ranked urgent: {p['routine_ranked_high']} of {p['n_routine']}",
        f"Top {q['k']} of the review queue: {q['watchdog_high_in_top_k']:g} sensitive vs {q['hash_high_in_top_k_expected']:g} with hash-only",
        "Changes that skipped review: 0",
    ]), 6.0))

    total = sum(t for _, t in shots)
    print(f"{len(shots)} frames, {total:.1f}s")
    with tempfile.TemporaryDirectory() as tmp:
        lst = Path(tmp) / "list.txt"
        with lst.open("w") as f:
            for i, (img, t) in enumerate(shots):
                path = Path(tmp) / f"f{i:04d}.png"
                img.save(path)
                f.write(f"file '{path}'\nduration {t}\n")
            f.write(f"file '{path}'\n")
        mp4 = ROOT / "demo" / "watchdog_demo.mp4"
        gif = ROOT / "demo" / "watchdog_demo.gif"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-vf", "fps=10,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-movflags", "+faststart", str(mp4)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
                        "fps=6,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48[p];[b][p]paletteuse=dither=none",
                        str(gif)], check=True)
    print(f"wrote {mp4} and {gif}")


if __name__ == "__main__":
    main()
