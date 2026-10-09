# BedAlert intro video

A ~3-minute animated explainer: what "no bed syndrome" is, the numbers behind it, and
what BedAlert is building. Narrated (AI voice) with on-screen captions.

- `RECORDING_SCRIPT.md`: numbered lines + instructions for recording your own voice
- `NARRATION.md`: the same script with performance notes
- `script.json`: the same text, plus how the AI voice should pronounce it
- `scenes.html`: the scenes and their timing
- `anim.js`: the animated illustrations (street, car, ambulance, avatars, maps)
- `narrate.py`, `pad.py`, `render.py`: build steps

The rendered MP4 is not committed (`out/` is ignored).

## Rebuild

Needs Python 3.11, Chromium (Playwright) and these packages:
`pip install kokoro-onnx soundfile playwright imageio-ffmpeg numpy`.
Voice model: `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the
kokoro-onnx GitHub releases (`model-files-v1.0`). Fonts: `npm pack
@fontsource/inter @fontsource/space-grotesk @fontsource/ibm-plex-mono`
and unpack them into one folder.

```bash
python narrate.py kokoro-v1.0.onnx voices-v1.0.bin build/          # voice + timings
python pad.py <duration> <solution-scene-start> build/pad.wav   # both from build/timings.json
python render.py build/ <fonts-folder> out/bedalert-no-bed-syndrome.mp4
```

Vertical (9:16) version for TikTok / Reels / Shorts: add `--portrait`:

```bash
python render.py build/ <fonts-folder> out/bedalert-no-bed-syndrome-vertical.mp4 --portrait
```

## Using your own voice

1. Record `RECORDING_SCRIPT.md` on your phone: every numbered line in order,
   with about 2 seconds of silence between lines, in one take.
2. Put the file in `media/intro-video/voice/` (any audio format).
3. Replace step 1 of the rebuild (`narrate.py`) with:

```bash
python import_voice.py voice/<your-file> build/
```

It cleans up the audio, cuts it at your pauses, matches each piece to its
line, and writes the same `narration.wav` + `timings.json`, so the
animation and captions follow your pacing. Then run `pad.py` and
`render.py` as usual. If it can't match the lines (a line skipped, or a long
pause in the middle of a line), it tells you what it found.

To change a name or a sentence, edit `script.json` (and `scenes.html` for
on-screen text such as the credits), then rebuild all three steps.

## Sources for the statistics

Listed on the final slide of the video and here:

1. Charles Amissah case: Graphic Online, Citi Newsroom, Ghanaian Times
   (Feb 2026); HeFRA investigation (16 Feb 2026); Ministry of Health committee
   findings, "118-minute referral loop" (May 2026).
2. 0.7–0.9 hospital beds per 1,000 people: World Bank WDI (0.7); GRNMA
   statement via Ghana News Agency (27 Mar 2026); Ashesi / Reach Alliance
   "No Bed Syndrome" study (0.9, 2021).
3. 120–150% occupancy at major hospitals: GRNMA statement (Mar 2026).
4. About 42 ambulances available in Greater Accra: National Ambulance Service
   dispatch head, Citi Newsroom (Jun 2025). Population: Ghana 2021 Census.

## 60-second teaser

Cut from a rendered full video at line boundaries, with crossfades:

```bash
python teaser.py out/bedalert-no-bed-syndrome-vertical-robert.mp4 out/bedalert-teaser-vertical-robert.mp4 \
  0.0-5.7 7.4-15.7 23.0-48.4 93.5-102.9 186.7-189.6 235.85-245.1
```

Hook → accident → ambulance turned away three times (118 minutes) →
BedAlert reveal → "Together, we can end no bed syndrome" → Robert's closing
line and logo. Times are for Robert's voiced render; take new ones from
`build/timings.json` if the narration changes.
