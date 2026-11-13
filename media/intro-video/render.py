"""Render scenes.html + narration into an MP4.

    python render.py <build_dir> <fonts_dir> <out.mp4> [--portrait] [--scenes file.html] [--assets dir] [--preview t1,t2,...]

--portrait renders the vertical 1080x1920 (TikTok / Reels / Shorts) layout.
--scenes uses another scene file instead of scenes.html (anim.js is still
copied next to it); --assets copies a folder of images to build/assets.

build_dir must contain narration.wav and timings.json (from narrate.py).
"""
import json
import pathlib
import shutil
import subprocess
import sys

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent
args = sys.argv[1:]
portrait = "--portrait" in args
if portrait:
    args.remove("--portrait")


def _opt(name, default=None):
    if name in args:
        i = args.index(name)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


scenes_file = pathlib.Path(_opt("--scenes", HERE / "scenes.html"))
assets = _opt("--assets")
build, fonts, out = pathlib.Path(args[0]), pathlib.Path(args[1]), pathlib.Path(args[2])
preview = [float(x) for x in args[4].split(",")] if len(args) > 4 and args[3] == "--preview" else None
W, H = (1080, 1920) if portrait else (1920, 1080)
FPS = 30
CHROME = str(next(iter(sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome"))), ""))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

(build / "fonts").mkdir(exist_ok=True)
for f in fonts.rglob("*-latin-[4-7]00-normal.woff2"):
    shutil.copy(f, build / "fonts" / f.name)
shutil.copy(scenes_file, build / "scenes.html")
if assets:
    shutil.copytree(assets, build / "assets", dirs_exist_ok=True)
shutil.copy(HERE / "anim.js", build / "anim.js")
timings = json.loads((build / "timings.json").read_text())
duration = timings["duration"]

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME if CHROME and pathlib.Path(CHROME).exists() else None)
    page = browser.new_page(viewport={"width": W, "height": H})
    page.add_init_script(f"window.TIMINGS = {json.dumps(timings)};")
    taps = build / "assets" / "taps.json"  # tap positions from update2/capture.py
    if taps.exists():
        page.add_init_script(f"window.TAPS = {taps.read_text()};")
    page.on("pageerror", lambda e: print("PAGE ERROR:", e))
    page.on("console", lambda m: print("CONSOLE:", m.text) if m.type == "error" else None)
    page.goto((build / "scenes.html").as_uri())
    page.evaluate("document.fonts.ready")
    if preview:
        for t in preview:
            page.evaluate(f"render({t})")
            page.screenshot(path=str(build / f"preview{'_v' if portrait else ''}_{t:06.1f}.png"))
        print("previews written")
        sys.exit(0)
    video_only = build / "video_only.mp4"
    enc = subprocess.Popen(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", str(video_only)],
        stdin=subprocess.PIPE,
    )
    frames = int(duration * FPS) + 1
    for i in range(frames):
        page.evaluate(f"render({i / FPS})")
        enc.stdin.write(page.screenshot(type="jpeg", quality=92))
        if i % 300 == 0:
            print(f"frame {i}/{frames}", flush=True)
    enc.stdin.close()
    enc.wait()
    browser.close()

# Mix: narration normalised for speech, with a quiet synthesized pad underneath.
subprocess.run(
    [FFMPEG, "-y", "-loglevel", "error", "-i", str(video_only), "-i", str(build / "narration.wav"), "-i", str(build / "pad.wav"),
     "-filter_complex",
     "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[v];[2:a]volume=0.26,aresample=48000[m];"
     "[v][m]amix=inputs=2:duration=first:normalize=0[a]",
     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
    check=True,
)
print("wrote", out)
