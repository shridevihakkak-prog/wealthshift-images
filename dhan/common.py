"""Shared by dhan/render.py and the poster (wealthshift-bot). Standard library only."""
import hashlib, json

RENDER_VERSION = "d1"  # bump to re-render every unposted night after a design change
CAPTION_ONLY = {"Question", "approved", "Date", "Series"}
SLIDES = 5
RAW = "https://raw.githubusercontent.com/shridevihakkak-prog/wealthshift-images/main/dhan/slides"


def data_hash(r, cfg):
    data = {k: v for k, v in r.items() if k not in CAPTION_ONLY}
    payload = json.dumps(data | {"v": RENDER_VERSION, "ebook": cfg.get("ebook_live", False)},
                         sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def slide_urls(r):
    return [f"{RAW}/{r['Id']}/Slide_{n}.jpg" for n in range(1, SLIDES + 1)]
