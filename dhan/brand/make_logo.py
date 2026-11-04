"""Diya-flame logo for Dhan Dhyaan: SVG master + PNGs (profile photo 1080, small 320)."""
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE = Path(__file__).resolve().parent
SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
<rect width="200" height="200" fill="#123B2E"/>
<circle cx="100" cy="100" r="70" fill="none" stroke="#E8A317" stroke-width="6"/>
<path d="M100 48c18 24 27 40 27 56a27 27 0 0 1-54 0c0-16 9-32 27-56z" fill="#E8A317"/>
<path d="M100 82c7 10 10 16 10 22a10 10 0 0 1-20 0c0-6 3-12 10-22z" fill="#123B2E"/>
<path d="M66 150h68" stroke="#E8A317" stroke-width="6" stroke-linecap="round"/>
</svg>'''
(HERE / "dhan-dhyaan-logo.svg").write_text(SVG, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch()
    for size in (1080, 320):
        pg = b.new_page(viewport={"width": size, "height": size})
        pg.set_content(f'<body style="margin:0">{SVG.replace("<svg ", f"<svg width={size} height={size} ")}</body>')
        pg.screenshot(path=str(HERE / f"dhan-dhyaan-logo-{size}.png"), clip={"x": 0, "y": 0, "width": size, "height": size})
    b.close()
print("logo written")
