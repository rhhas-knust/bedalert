"""Use a real voice recording instead of the AI narrator.

Record yourself reading RECORDING_SCRIPT.md: every numbered line, in order,
with a clear pause (about 2 seconds of silence) between lines. Any format
works (m4a, mp3, wav, ogg, opus...). Then:

    python import_voice.py <recording> <build_dir> [<whisper_model_dir> | <spans.json>]

A spans.json (see voice/robert-narration.spans.json) gives hand-checked
[start, end] seconds for every line, plus optional "extra" unscripted parts
placed after a given scene. If the pauses between lines are too short to find, pass a sherpa-onnx Whisper
model folder (e.g. sherpa-onnx-whisper-base.en from the sherpa-onnx GitHub
"asr-models" release) and the lines are found by speech recognition instead.

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


# ---------------------------------------------------------------- speech-recognition alignment
# Used when the pauses between lines are too short to tell apart from pauses
# inside a line: cut at every short pause, transcribe each piece with Whisper
# (sherpa-onnx), then pick the grouping of pieces that best matches the script.

def chunks(audio: np.ndarray, min_gap: float = 0.22) -> list:
    n = int(FRAME * SR)
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    thresh = min(np.median(db) - 16, np.percentile(db, 30))
    voiced = db > thresh
    regs, start, quiet = [], None, 0
    for i, v in enumerate(voiced):
        if v:
            start = i if start is None else start
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * FRAME >= min_gap:
                regs.append((start * FRAME, (i - quiet + 1) * FRAME)); start, quiet = None, 0
    if start is not None:
        regs.append((start * FRAME, len(voiced) * FRAME))
    regs = [(a, b) for a, b in regs if b - a >= 0.12]
    # Lines read back-to-back can land in one long piece: split long pieces at
    # their quietest moment until each is short enough to hold ~one phrase.
    smooth = np.convolve(db, np.ones(5) / 5, mode="same")
    out, todo = [], list(regs)
    while todo:
        a, b = todo.pop(0)
        if b - a <= 2.6:
            out.append((a, b)); continue
        i0, i1 = int((a + 0.6) / FRAME), int((b - 0.6) / FRAME)
        k = i0 + int(np.argmin(smooth[i0:i1]))
        todo[:0] = [(a, k * FRAME), (k * FRAME + FRAME, b)]
    return out


def words(text: str) -> list:
    import re
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("-", " ")).split()


def transcribe(audio: np.ndarray, regs: list, model_dir: str) -> list:
    import sherpa_onnx
    d = pathlib.Path(model_dir)
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(next(d.glob("*encoder.int8.onnx"))), decoder=str(next(d.glob("*decoder.int8.onnx"))),
        tokens=str(next(d.glob("*tokens.txt"))), language="en", task="transcribe", num_threads=4)
    out = []
    for a, b in regs:
        s = rec.create_stream()
        s.accept_waveform(SR, audio[max(0, int((a - 0.1) * SR)): int((b + 0.1) * SR)])
        rec.decode_stream(s)
        out.append(words(s.result.text))
    return out


def align(chunk_words: list, lines: list, max_span: int = 14) -> list:
    """DP: give each script line a run of consecutive chunks; chunks may be
    skipped (stray words, coughs). Returns [(first_chunk, last_chunk)] per line."""
    from difflib import SequenceMatcher
    M, N = len(chunk_words), len(lines)
    target = [words(l) for l in lines]
    NEG = -1e9
    dp = [[NEG] * (N + 1) for _ in range(M + 1)]
    back = [[None] * (N + 1) for _ in range(M + 1)]
    dp[0][0] = 0.0
    for i in range(1, M + 1):
        for j in range(0, N + 1):
            if dp[i - 1][j] > NEG and dp[i - 1][j] - 0.35 > dp[i][j]:          # skip chunk i
                dp[i][j], back[i][j] = dp[i - 1][j] - 0.35, ("skip", i - 1)
            if j == 0:
                continue
            for k in range(max(0, i - max_span), i):
                if dp[k][j - 1] <= NEG:
                    continue
                got = [w for c in chunk_words[k:i] for w in c]
                sm = SequenceMatcher(None, got, target[j - 1], autojunk=False)
                score = 2 * sum(b.size for b in sm.get_matching_blocks()) / (len(got) + len(target[j - 1]) or 1)
                v = dp[k][j - 1] + score * len(target[j - 1]) ** 0.5
                if v > dp[i][j]:
                    dp[i][j], back[i][j] = v, ("line", k)
    spans, i, j = [], M, N
    while j > 0:
        kind, k = back[i][j]
        if kind == "line":
            spans.append((k, i - 1)); j -= 1
        i = k
    return spans[::-1]


def split_lines_asr(audio: np.ndarray, texts: list, model_dir: str) -> list:
    regs = chunks(audio)
    cw = transcribe(audio, regs, model_dir)
    spans = align(cw, texts)
    for (a, b), t in zip(spans, texts):
        heard = " ".join(w for c in cw[a:b + 1] for w in c)
        print(f"  {regs[a][0]:6.1f}-{regs[b][1]:6.1f}s  {heard[:70]}")
    return [(regs[a][0], regs[b][1]) for a, b in spans]


def main() -> None:
    recording, out = sys.argv[1], pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    script = json.loads((HERE / "script.json").read_text())
    lines = [(scene, line) for scene in script["scenes"] for line in scene["lines"]]
    audio = load(recording)
    third = sys.argv[3] if len(sys.argv) > 3 else None
    spans = json.loads(pathlib.Path(third).read_text()) if third and third.endswith(".json") else None
    asr_model = None if spans else third
    extra = {e["after"]: e for e in (spans or {}).get("extra", [])}
    try:
        if spans:
            regs = [tuple(x) for x in spans["lines"]]
            if len(regs) != len(lines):
                raise SystemExit(f"Spans file has {len(regs)} lines, script has {len(lines)}")
        else:
            regs = split_lines(audio, len(lines))
    except SystemExit as exc:
        if not asr_model:
            raise SystemExit(str(exc) + "\nTip: pass a sherpa-onnx Whisper model folder as a third argument to align by speech recognition instead.")
        print("Pauses alone are not enough; aligning with speech recognition…")
        regs = split_lines_asr(audio, [l["text"] for _, l in lines], asr_model)

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
        if scene["id"] in extra:  # an unscripted part of the recording, e.g. a closing message
            e = extra[scene["id"]]
            clip = audio[int(e["span"][0] * SR): int(e["span"][1] * SR)]
            start, dur = t, len(clip) / SR
            track += [clip, np.zeros(int(e["pad"] * SR), dtype=np.float32)]
            t += dur + e["pad"]
            timings.append({"id": e["id"], "start": round(start, 3), "end": round(t, 3), "lines": []})

    sig = np.concatenate(track)
    sig = sig / max(1e-6, np.abs(sig).max()) * 0.9
    sf.write(out / "narration.wav", sig, SR)
    (out / "timings.json").write_text(json.dumps({"duration": round(t, 3), "scenes": timings}, indent=1))
    print(f"Matched {len(lines)} lines. Narration length: {t:.1f}s")


if __name__ == "__main__":
    main()
