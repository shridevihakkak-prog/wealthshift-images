"""Render Dhan Dhyaan carousels (5 slides, 1080x1350) from dhan/queue.json.

Output: dhan/slides/<Id>/Slide_1..5.jpg, plus dhan/slides/manifest.json holding a
hash of the data each folder was rendered from. Only changed entries re-render,
and the poster refuses to publish slides whose hash doesn't match the queue.

Fonts are bundled in dhan/_fonts (OFL), so rendering never needs the network.
Usage: python dhan/render.py [--force] [--only DD001,DD002] [--out DIR]
"""
import argparse, base64, hashlib, html, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import data_hash  # noqa: E402

REQUIRED = ["Id", "Night", "Label", "Hook", "Sub", "DoesLabel", "Does", "Line", "LineHi", "ActHead", "ActBody", "Question"]


def fonts():
    faces = [("Tiro", "TiroDevanagariHindi-Regular.ttf", "400", "normal"),
             ("Tiro", "TiroDevanagariHindi-Italic.ttf", "400", "italic"),
             ("Hind", "Hind-Regular.ttf", "400", "normal"), ("Hind", "Hind-Medium.ttf", "500", "normal"),
             ("Hind", "Hind-SemiBold.ttf", "600", "normal"), ("Hind", "Hind-Bold.ttf", "700", "normal")]
    out = []
    for fam, f, w, st in faces:
        b = base64.b64encode((HERE / "_fonts" / f).read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:{st};font-display:block;"
                   f"src:url(data:font/ttf;base64,{b}) format('truetype')}}")
    return "\n".join(out)


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden}
body{font-family:'Hind',sans-serif;display:flex;flex-direction:column;padding:84px 88px 64px}
.g{background:#123B2E;color:#F6EFE2}.c{background:#F6EFE2;color:#123B2E}
.top{display:flex;justify-content:space-between;align-items:center;font-size:26px;font-weight:600;letter-spacing:.14em;text-transform:uppercase}
.g .top{color:#9FB8AC}.c .top{color:#6E7F76}
.mark{display:flex;align-items:center;gap:14px;letter-spacing:.04em;text-transform:none;font-size:30px;font-weight:600}
.mark svg{width:46px;height:46px}
.mid{flex:1;display:flex;flex-direction:column;justify-content:center;gap:34px;min-height:0}
.serif{font-family:'Tiro',serif}
.say{line-height:1.1}
.tr{font-size:46px;color:#E8A317;font-style:italic;line-height:1.4}
.sub{font-size:42px;line-height:1.4;color:#B5CBC0;max-width:880px}
.c .sub{color:#4C6258}
.lab{font-size:28px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:#E8A317}
.c .lab{color:#B3362B;text-align:center}
.does{display:flex;flex-direction:column;gap:40px}
.does div{font-size:58px;line-height:1.2;font-weight:600}
.big{font-size:62px;line-height:1.2;font-weight:600}
.aff{line-height:1.12;text-align:center}
.hi{line-height:1.5;text-align:center;color:#B3362B}
.rule{width:120px;height:3px;background:#E8A317;margin:0 auto}
.steps{display:flex;flex-direction:column;gap:30px;font-size:44px;line-height:1.35}
.steps div{display:flex;gap:28px}.steps b{color:#E8A317;font-weight:700;min-width:44px}
.foot{display:flex;justify-content:space-between;align-items:center;gap:24px;font-size:28px;border-top:2px solid rgba(159,184,172,.35);padding-top:26px}
.c .foot{border-color:rgba(18,59,46,.18)}
.pill{background:#E8A317;color:#0B2A20;font-weight:700;padding:12px 26px;border-radius:40px;white-space:nowrap}
"""
MARK = ('<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="29" fill="none" stroke="#E8A317" stroke-width="3.5"/>'
        '<path d="M32 13c7 10 11 17 11 23a11 11 0 0 1-22 0c0-6 4-13 11-23z" fill="#E8A317"/>'
        '<path d="M32 27c3 4 4 7 4 9a4 4 0 0 1-8 0c0-2 1-5 4-9z" fill="{inner}"/>'
        '<path d="M19 50h26" stroke="#E8A317" stroke-width="3.5" stroke-linecap="round"/></svg>')


def size_for(text, steps):
    n = len(text)
    for limit, px in steps:
        if n <= limit:
            return px
    return steps[-1][1]


def slides(r, cfg):
    e = html.escape
    night = int(r["Night"])

    def top(dark):
        inner = "#123B2E" if dark else "#F6EFE2"
        return (f'<div class="top"><span class="mark">{MARK.replace("{inner}", inner)}Dhan Dhyaan</span>'
                f'<span>Night {night:02d}</span></div>')

    def foot(left, right="Swipe →"):
        return f'<div class="foot"><span>{left}</span><span>{right}</span></div>'

    hook_px = size_for(r["Hook"], [(26, 96), (40, 84), (56, 74), (999, 64)])
    hi = f'<div class="serif tr">{e(r["HookHi"])}</div>' if r.get("HookHi") else ""
    aff_px = size_for(r["Line"], [(34, 100), (46, 90), (999, 80)])
    hi_px = size_for(r["LineHi"], [(36, 58), (52, 52), (999, 46)])
    act_px = size_for(r["ActHead"], [(40, 64), (60, 58), (999, 52)])
    if cfg.get("ebook_live"):
        last = foot(f'The full 90-day practice · {e(cfg.get("price", "₹299"))}', '<span class="pill">Link in bio</span>')
    else:
        last = foot("A new line every night at 8", '<span class="pill">Follow for tomorrow</span>')
    return [
        ("g", f'{top(True)}<div class="mid"><div class="lab">{e(r["Label"])}</div>'
              f'<div class="serif say" style="font-size:{hook_px}px">{e(r["Hook"])}</div>{hi}'
              f'<div class="sub">{e(r["Sub"])}</div></div>{foot("Tonight’s line is on slide 3")}'),
        ("g", f'{top(True)}<div class="mid"><div class="lab">{e(r["DoesLabel"])}</div>'
              f'<div class="does">{"".join(f"<div>{e(x)}</div>" for x in r["Does"])}</div></div>'
              f'{foot("Tonight, a new line for it.")}'),
        ("c", f'{top(False)}<div class="mid"><div class="lab">Tonight\'s line</div>'
              f'<div class="serif aff" style="font-size:{aff_px}px">{e(r["Line"])}</div><div class="rule"></div>'
              f'<div class="serif hi" style="font-size:{hi_px}px">{e(r["LineHi"])}</div></div>'
              f'{foot("Save this for bedtime")}'),
        ("g", f'{top(True)}<div class="mid"><div class="lab">One small thing today</div>'
              f'<div class="big" style="font-size:{act_px}px">{e(r["ActHead"])}</div>'
              f'<div class="sub">{e(r["ActBody"])}</div></div>{foot("Small act. Real change.")}'),
        ("g", f'{top(True)}<div class="mid"><div class="lab">How to use tonight\'s line</div>'
              '<div class="steps"><div><b>1</b>Lie down. Three slow breaths, longer out than in.</div>'
              '<div><b>2</b>Say the line aloud five times, in English or Hindi.</div>'
              '<div><b>3</b>Feel it as already true: shoulders loose, no clench.</div></div>'
              '<div class="sub" style="font-size:36px">Not magic, and not financial advice. Repetition changes what you notice, ask for and keep.</div></div>'
              f'{last}'),
    ]


def validate(rows):
    errs, ids = [], set()
    for r in rows:
        for k in REQUIRED:
            if not r.get(k):
                errs.append(f"{r.get('Id', '?')}: missing {k}")
        if len(r.get("Does", [])) != 3:
            errs.append(f"{r.get('Id')}: Does needs exactly 3 lines")
        if r.get("Id") in ids:
            errs.append(f"duplicate Id {r.get('Id')}")
        ids.add(r.get("Id"))
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--out", default=str(HERE / "slides"))
    a = ap.parse_args()
    rows = json.loads((HERE / "queue.json").read_text(encoding="utf-8"))
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    errs = validate(rows)
    if errs:
        sys.exit("queue.json invalid:\n  " + "\n  ".join(errs))
    if a.only:
        keep = set(a.only.split(","))
        rows = [r for r in rows if r["Id"] in keep]
    out = Path(a.out)
    mpath = out / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    head = f"<!doctype html><html><head><meta charset='utf-8'><style>{fonts()}{CSS}</style></head>"
    problems, built = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for r in rows:
            h, folder = data_hash(r, cfg), out / r["Id"]
            if not a.force and manifest.get(r["Id"]) == h and all((folder / f"Slide_{n}.jpg").exists() for n in range(1, 6)):
                continue
            folder.mkdir(parents=True, exist_ok=True)
            for n, (cls, body) in enumerate(slides(r, cfg), 1):
                pg.set_content(f"{head}<body class='{cls}'>{body}</body></html>", wait_until="load")
                pg.evaluate("document.fonts.ready")
                over = pg.evaluate("""() => { const m = document.querySelector('.mid');
                    return (m.scrollHeight > m.clientHeight + 2) || document.body.scrollHeight > 1350 ||
                      [...document.querySelectorAll('.foot span')].some(s => s.scrollWidth > s.clientWidth + 2); }""")
                if over:
                    problems.append(f"{r['Id']} slide {n}")
                pg.screenshot(path=str(folder / f"Slide_{n}.jpg"), type="jpeg", quality=92)
            manifest[r["Id"]] = h
            built += 1
            print("rendered", r["Id"], h)
        b.close()
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    print(built, "rendered of", len(rows))
    if problems:
        sys.exit("Text does not fit: " + ", ".join(problems))


if __name__ == "__main__":
    main()
