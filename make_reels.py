#!/usr/bin/env python3
"""Composite Wealthshift affirmation cards onto the animated coin background.

Run by .github/workflows/build_reels.yml. Reads reel_bg.mp4 (1080x1350, coins on
black, music baked in) plus the cards in wealthshift/, and writes 1080x1920 reels
to reels/.

  python make_reels.py --start 1 --end 300
"""
import argparse, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFilter

W, H      = 1080, 1920
CARD_W    = 940      # card width inside the frame
BG_DIM    = 0.45     # darkening applied to the background behind the card
FRONT     = 0.92     # strength of coins passing in front, outside the card
OVER_CARD = 0.30     # fraction of that allowed across the card itself
LOOPS     = 2        # repeats of the 5s background clip
DURATION  = 10.0     # final reel length, seconds

BG    = "reel_bg.mp4"
CARDS = "wealthshift"
OUT   = "reels"

# The background is 1080x1350; it is PADDED to 1080x1920 rather than scaled, so the
# coins keep the size that was approved. The black padding is indistinguishable
# from the footage's own black background, and those strips sit behind Instagram's
# UI anyway.
#
# Everything composites in RGB (gbrp). Blending in YUV operates on the chroma
# planes independently and turns the entire frame purple.
FILTER = (
    f"[0:v]pad={W}:{H}:0:(oh-ih)/2:black,format=gbrp,split=2[b1][b2];"
    f"[b1]colorlevels=rimax={BG_DIM}:gimax={BG_DIM}:bimax={BG_DIM}[dim];"
    "[1:v]format=gbrap[card];"
    "[dim][card]overlay=0:0:format=rgb[base];"
    "[2:v]format=gbrp[mask];"
    "[b2][mask]blend=all_mode=multiply[front];"
    f"[base][front]blend=all_mode=screen:all_opacity={FRONT},format=yuv420p[v]"
)


def build_mask(dst, card_h):
    """Grey over the card, white elsewhere, soft edged.

    Multiplied into the front-coin layer before it is screened on, so coins stay
    bright around the card but drop back across the text."""
    m = Image.new("L", (W, H), 255)
    x, y = (W - CARD_W) // 2, (H - card_h) // 2
    ImageDraw.Draw(m).rounded_rectangle(
        [x, y, x + CARD_W, y + card_h], 24, fill=int(255 * OVER_CARD))
    m.filter(ImageFilter.GaussianBlur(55)).convert("RGB").save(dst)
    return dst


def build_card(src, dst):
    """Card resized to CARD_W with a soft drop shadow, full-frame RGBA."""
    im = Image.open(src).convert("RGB")
    ch = round(CARD_W * im.height / im.width)
    im = im.resize((CARD_W, ch), Image.LANCZOS)
    x, y = (W - CARD_W) // 2, (H - ch) // 2

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x - 8, y - 8, x + CARD_W + 8, y + ch + 8], 20, fill=190)
    canvas.paste(Image.new("RGBA", (W, H), (0, 0, 0, 255)), (0, 0),
                 shadow.filter(ImageFilter.GaussianBlur(30)))
    canvas.paste(im, (x, y))
    canvas.save(dst)
    return dst, ch


def render(card_png, mask_png, out):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-stream_loop", str(LOOPS - 1), "-i", BG,
         "-loop", "1", "-i", card_png, "-loop", "1", "-i", mask_png,
         "-filter_complex", FILTER, "-map", "[v]", "-map", "0:a?",
         "-t", str(DURATION), "-c:v", "libx264", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-crf", "21", "-r", "30",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out],
        check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=300)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--force", action="store_true",
                    help="rebuild reels that already exist")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    tmp = ".build"; os.makedirs(tmp, exist_ok=True)

    ids = ["%04d" % i for i in range(a.start, a.end + 1)]
    ids = [i for i in ids if os.path.exists(f"{CARDS}/Wealthshift-{i}.jpg")]
    if not a.force:
        ids = [i for i in ids if not os.path.exists(f"{OUT}/Wealthshift-{i}.mp4")]
    if not ids:
        print("Nothing to build."); return

    probe = Image.open(f"{CARDS}/Wealthshift-{ids[0]}.jpg")
    mask = build_mask(f"{tmp}/mask.png",
                      round(CARD_W * probe.height / probe.width))

    def one(i):
        png, _ = build_card(f"{CARDS}/Wealthshift-{i}.jpg", f"{tmp}/{i}.png")
        render(png, mask, f"{OUT}/Wealthshift-{i}.mp4")
        os.remove(png)
        return i

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for n, i in enumerate(ex.map(one, ids), 1):
            print(f"[{n}/{len(ids)}] Wealthshift-{i}.mp4", flush=True)


if __name__ == "__main__":
    main()
