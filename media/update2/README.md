# BedAlert update video #2: Phase 2 done (vertical, ~75 s)

Real screens of the four apps (captured from a local run with demo data),
shown in a phone frame and as cards, with taps, captions and narration.

- `capture.py`: walks the real flows in a browser and saves the screenshots + `taps.json`
- `script.json`: narration lines (`text` = caption, `say` = AI pronunciation)
- `RECORDING_SCRIPT.md`: the same lines, for recording your own voice
- `scenes.html`: the scenes; rendered with `../intro-video/render.py`
- `TIKTOK.md`: caption, hashtags, cover text

## Rebuild

Tools as in `../intro-video/README.md` (Python packages, Kokoro model, fonts).

```bash
# 1. API (dev mode, fresh demo data) + built apps, as for frontend/e2e/smoke.py
python capture.py http://localhost:4173 build/shots

# 2. Narration: AI voice...
cd ../intro-video
python narrate.py kokoro-v1.0.onnx voices-v1.0.bin build-u2/ ../update2/script.json
#    ...or your own recording of RECORDING_SCRIPT.md
python import_voice.py ../update2/voice/<file> build-u2/ --script ../update2/script.json

# 3. Music + video
python pad.py <duration from build-u2/timings.json> 0 build-u2/pad.wav
python render.py build-u2/ <fonts> out/bedalert-update-phase2-vertical.mp4 --portrait \
  --scenes ../update2/scenes.html --assets ../update2/build/shots
```

Screenshots and videos are not committed; `capture.py` recreates them.
