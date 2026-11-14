"""Render the TikTok cover (cover.html) to a 1080x1920 PNG.

    python cover.py <shots_dir from capture.py> <fonts_dir> <out.png>
"""
import pathlib
import shutil
import sys
import tempfile

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
shots, fonts, out = (pathlib.Path(a) for a in sys.argv[1:4])
CHROME = next(iter(sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome"))), None)

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "fonts").mkdir()
    for f in fonts.rglob("*-latin-[4-7]00-normal.woff2"):
        shutil.copy(f, d / "fonts" / f.name)
    shutil.copytree(shots, d / "assets")
    shutil.copy(HERE / "cover.html", d / "cover.html")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(CHROME) if CHROME else None)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto((d / "cover.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out))
        browser.close()
print("wrote", out)
