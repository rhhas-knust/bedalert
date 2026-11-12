"""Assemble a new narration from lines already recorded, in any order.

    python compose_voice.py <sequence.json> <build_dir>

sequence.json:
  {
    "recording": "voice/robert-narration.aac",
    "spans": "voice/robert-narration.spans.json",
    "scenes": [
      {"id": "pioneers", "lines": [32], "lead": 0.8, "pad": 0.8},
      {"id": "outro", "span": [196.6, 217.3], "pad": 2.5, "cues": [...]},
      ...
    ]
  }

"lines" are 1-based line numbers from RECORDING_SCRIPT.md (= script.json
order); captions use those lines' text. "span" takes raw seconds from the
recording (for unscripted parts) and has no captions. Writes narration.wav
and timings.json for render.py, like narrate.py / import_voice.py.
"""
import json
import pathlib
import sys

import numpy as np
import soundfile as sf

from import_voice import GAP, SR, load

HERE = pathlib.Path(__file__).parent


def main() -> None:
    seq = json.loads(pathlib.Path(sys.argv[1]).read_text())
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads((HERE / "script.json").read_text())
    lines = [line for scene in script["scenes"] for line in scene["lines"]]
    spans = json.loads((HERE / seq["spans"]).read_text())["lines"]
    audio = load(str(HERE / seq["recording"]))

    pad = int(0.08 * SR)
    track, timings, t = [], [], 0.0
    for sc in seq["scenes"]:
        lead = sc.get("lead", 0.0)
        start = t
        track.append(np.zeros(int(lead * SR), dtype=np.float32))
        t += lead
        entry = {"id": sc["id"], "start": round(start, 3), "lines": []}
        if "span" in sc:
            a, b = sc["span"]
            clip = audio[int(a * SR): int(b * SR)]
            track.append(clip)
            t += len(clip) / SR
        for n in sc.get("lines", []):
            a, b = spans[n - 1]
            clip = audio[max(0, int(a * SR) - pad): int(b * SR) + pad].copy()
            fade = min(len(clip) // 4, int(0.03 * SR))
            clip[:fade] *= np.linspace(0, 1, fade)
            clip[-fade:] *= np.linspace(1, 0, fade)
            dur = len(clip) / SR
            entry["lines"].append({"text": lines[n - 1]["text"], "start": round(t, 3), "end": round(t + dur, 3)})
            gap = sc.get("gaps", {}).get(str(n), lines[n - 1].get("gap", GAP))
            track += [clip, np.zeros(int(gap * SR), dtype=np.float32)]
            t += dur + gap
        track.append(np.zeros(int(sc.get("pad", 0.6) * SR), dtype=np.float32))
        t += sc.get("pad", 0.6)
        entry["end"] = round(t, 3)
        if "cues" in sc:
            entry["cues"] = sc["cues"]
        timings.append(entry)

    sig = np.concatenate(track)
    sig = sig / max(1e-6, np.abs(sig).max()) * 0.9
    sf.write(out / "narration.wav", sig, SR)
    (out / "timings.json").write_text(json.dumps({"duration": round(t, 3), "scenes": timings}, indent=1))
    print(f"Narration length: {t:.1f}s")


if __name__ == "__main__":
    main()
