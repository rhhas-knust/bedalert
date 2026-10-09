"""Cut a short teaser from a rendered full video, with crossfades.

    python teaser.py <full.mp4> <out.mp4> <start-end> [<start-end> ...]

Times are seconds in the full video. Pick cuts at line boundaries (see
build_dir/timings.json) so captions are never cut mid-sentence.
"""
import subprocess
import sys

import imageio_ffmpeg

FADE = 0.35
src, out, spans = sys.argv[1], sys.argv[2], [tuple(map(float, s.split("-"))) for s in sys.argv[3:]]
parts, v, a = [], [], []
for i, (s, e) in enumerate(spans):
    parts.append(f"[0:v]trim={s}:{e},setpts=PTS-STARTPTS,fps=30[v{i}];[0:a]atrim={s}:{e},asetpts=PTS-STARTPTS[a{i}]")
chain, prev_v, prev_a, total = [], "v0", "a0", spans[0][1] - spans[0][0]
for i in range(1, len(spans)):
    off = total - FADE
    chain.append(f"[{prev_v}][v{i}]xfade=transition=fade:duration={FADE}:offset={off:.3f}[vx{i}]")
    chain.append(f"[{prev_a}][a{i}]acrossfade=d={FADE}[ax{i}]")
    prev_v, prev_a = f"vx{i}", f"ax{i}"
    total = off + (spans[i][1] - spans[i][0])
graph = ";".join(parts + chain + [f"[{prev_a}]afade=t=out:st={total - 0.8:.3f}:d=0.8[aout]"])
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src, "-filter_complex", graph,
                "-map", f"[{prev_v}]", "-map", "[aout]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
print(f"wrote {out} ({total:.1f}s)")
