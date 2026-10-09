"""Use a real voice recording instead of the AI narrator.

Record yourself reading RECORDING_SCRIPT.md: every numbered line, in order,
with a clear pause (about 2 seconds of silence) between lines. Any format
works (m4a, mp3, wav, ogg, opus...). Then:

    python import_voice.py <recording> <build_dir>

This cuts the recording at the pauses, matches each piece to its line in
script.json, and writes build_dir/narration.wav + build_dir/timings.json in
the same shape narrate.py produces, so render.py works unchanged and the
captions follow your timing.
"""
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg
import numpy as np
import soundfile as sf

HERE = pathlib.Path(__file__).parent
SR = 24000
FRAME = 0.02          # 20 ms analysis frames
GAP = 0.35            # default silence between lines in the video (same as narrate.py)


def load(path: str) -> np.ndarray:
    """Decode any audio file to mono 24 kHz float, with gentle clean-up:
    rumble filter + light noise reduction."""
    raw = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
         "-af", "highpass=f=80,afftdn=nf=-25", "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def segments(audio: np.ndarray, min_gap: float, thresh_db: float) -> list:
    """Speech regions separated by at least `min_gap` seconds of quiet."""
    n = int(FRAME * SR)
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    floor = np.percentile(db, 10)
    voiced = db > max(floor + thresh_db, db.max() - 45)
    regions, start, quiet = [], None, 0
    for i, v in enumerate(voiced):
        if v:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * FRAME >= min_gap:
                regions.append((start, i - quiet + 1))
                start, quiet = None, 0
    if start is not None:
        regions.append((start, len(voiced)))
    return [(a * FRAME, b * FRAME) for a, b in regions if (b - a) * FRAME >= 0.3]


def split_lines(audio: np.ndarray, expected: int) -> list:
    """Find the pause length that yields exactly one region per script line."""
    for thresh in (12, 9, 15, 6):
        for gap in (0.6, 0.8, 1.0, 1.2, 1.5, 0.45, 1.8, 2.2):
            regs = segments(audio, gap, thresh)
            if len(regs) == expected:
                return regs
    regs = segments(audio, 1.0, 12)
    raise SystemExit(
        f"Found {len(regs)} spoken parts but the script has {expected} lines.\n"
        "Check that every line was read once, in order, with a ~2 second pause between lines "
        "(and no long pauses inside a line). Parts found (seconds): "
        + ", ".join(f"{a:.1f}-{b:.1f}" for a, b in regs)
    )


def main() -> None:
    recording, out = sys.argv[1], pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads((HERE / "script.json").read_text())
    lines = [(scene, line) for scene in script["scenes"] for line in scene["lines"]]
    audio = load(recording)
    regs = split_lines(audio, len(lines))

    pad = int(0.08 * SR)
    track, timings, t, k = [], [], 0.0, 0
    for scene in script["scenes"]:
        start, scene_lines = t, []
        for line in scene["lines"]:
            a, b = regs[k]
            k += 1
            clip = audio[max(0, int(a * SR) - pad): int(b * SR) + pad]
            fade = min(len(clip) // 4, int(0.03 * SR))
            clip[:fade] *= np.linspace(0, 1, fade)
            clip[-fade:] *= np.linspace(1, 0, fade)
            dur = len(clip) / SR
            scene_lines.append({"text": line["text"], "start": round(t, 3), "end": round(t + dur, 3)})
            gap = line.get("gap", GAP)
            track += [clip, np.zeros(int(gap * SR), dtype=np.float32)]
            t += dur + gap
        track.append(np.zeros(int(scene["pad"] * SR), dtype=np.float32))
        t += scene["pad"]
        timings.append({"id": scene["id"], "start": round(start, 3), "end": round(t, 3), "lines": scene_lines})

    sig = np.concatenate(track)
    sig = sig / max(1e-6, np.abs(sig).max()) * 0.9
    sf.write(out / "narration.wav", sig, SR)
    (out / "timings.json").write_text(json.dumps({"duration": round(t, 3), "scenes": timings}, indent=1))
    print(f"Matched {len(lines)} lines. Narration length: {t:.1f}s")


if __name__ == "__main__":
    main()
