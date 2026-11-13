"""Generate narration WAVs (one per line) + timings.json with Kokoro TTS.

    python narrate.py <kokoro-v1.0.onnx> <voices-v1.0.bin> <out_dir> [script.json]

The script defaults to script.json next to this file.
"""
import json
import pathlib
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

HERE = pathlib.Path(__file__).parent
model, voices, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
script = json.loads(pathlib.Path(sys.argv[4] if len(sys.argv) > 4 else HERE / "script.json").read_text())
kokoro = Kokoro(model, voices)

GAP = 0.35  # silence between lines
SR = 24000
track, timings, t = [], [], 0.0
for scene in script["scenes"]:
    start = t
    lines = []
    for line in scene["lines"]:
        audio, sr = kokoro.create(line["say"], voice=script["voice"], speed=line.get("speed", scene.get("speed", script["speed"])), lang="en-us")
        assert sr == SR
        dur = len(audio) / SR
        lines.append({"text": line["text"], "start": round(t, 3), "end": round(t + dur, 3)})
        track.append(audio.astype(np.float32))
        track.append(np.zeros(int(line.get("gap", GAP) * SR), dtype=np.float32))
        gap = line.get("gap", GAP)
        t += dur + gap
    track.append(np.zeros(int(scene["pad"] * SR), dtype=np.float32))
    t += scene["pad"]
    timings.append({"id": scene["id"], "start": round(start, 3), "end": round(t, 3), "lines": lines})

sf.write(out / "narration.wav", np.concatenate(track), SR)
(out / "timings.json").write_text(json.dumps({"duration": round(t, 3), "scenes": timings}, indent=1))
print(f"Narration length: {t:.1f}s")
