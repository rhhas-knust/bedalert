"""Render scenes.html + narration into an MP4.

    python render.py <build_dir> <fonts_dir> <out.mp4> [--preview t1,t2,...]

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
build, fonts, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
preview = [float(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 and sys.argv[4] == "--preview" else None
FPS = 30
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

(build / "fonts").mkdir(exist_ok=True)
for f in fonts.rglob("*-latin-[4-7]00-normal.woff2"):
    shutil.copy(f, build / "fonts" / f.name)
shutil.copy(HERE / "scenes.html", build / "scenes.html")
shutil.copy(HERE / "anim.js", build / "anim.js")
timings = json.loads((build / "timings.json").read_text())
duration = timings["duration"]

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME if pathlib.Path(CHROME).exists() else None)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.add_init_script(f"window.TIMINGS = {json.dumps(timings)};")
    page.on("pageerror", lambda e: print("PAGE ERROR:", e))
    page.on("console", lambda m: print("CONSOLE:", m.text) if m.type == "error" else None)
    page.goto((build / "scenes.html").as_uri())
    page.evaluate("document.fonts.ready")
    if preview:
        for t in preview:
            page.evaluate(f"render({t})")
            page.screenshot(path=str(build / f"preview_{t:06.1f}.png"))
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
     "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[v];[2:a]volume=0.22,aresample=48000[m];"
     "[v][m]amix=inputs=2:duration=first:normalize=0[a]",
     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
    check=True,
)
print("wrote", out)
