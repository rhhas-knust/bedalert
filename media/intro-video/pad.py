"""Synthesize the music bed (no samples, no licensing issues): a slow, sombre
pad for the problem, then a brighter, upbeat progression with plucked
arpeggios and a soft pulse from the moment BedAlert is introduced.

    python pad.py <seconds> <switch_seconds> <out.wav>
"""
import sys

import numpy as np
import soundfile as sf

secs, switch, out = float(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
SR = 48000
t = np.arange(int(secs * SR)) / SR

# Part 1: A minor -> F -> C -> G pad, 8 s per chord.
sombre = np.zeros_like(t)
chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [130.81, 164.81, 196.0], [196.0, 246.94, 293.66]]
for k in range(int(np.ceil(secs / 8)) + 1):
    env = np.clip(1 - np.abs((t - k * 8 - 4) / 6), 0, 1) ** 1.5
    for f in chords[k % 4]:
        for d in (-0.6, 0.6):
            sombre += env * np.sin(2 * np.pi * (f + d) * t) * 0.05
        sombre += env * np.sin(np.pi * f * t) * 0.04

# Part 2: C - G - Am - F at 104 bpm, two bars per chord.
bpm = 104
beat = 60 / bpm
up = np.zeros_like(t)
prog = [[261.63, 329.63, 392.0], [196.0, 246.94, 293.66], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63]]
bar = 4 * beat
u = t - switch
for i in range(int((secs - switch) / (beat / 2)) + 2):            # eighth-note arpeggio
    start = switch + i * beat / 2
    chord = prog[int(i * (beat / 2) / (2 * bar)) % 4]
    f = chord[i % 3] * (2 if (i // 3) % 2 else 1)
    idx = (t >= start) & (t < start + 0.6)
    tt = t[idx] - start
    up[idx] += np.exp(-tt * 7) * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * 0.10
for i in range(int((secs - switch) / beat) + 2):                  # soft pulse on each beat
    start = switch + i * beat
    idx = (t >= start) & (t < start + 0.25)
    tt = t[idx] - start
    up[idx] += np.exp(-tt * 18) * np.sin(2 * np.pi * (55 + 40 * np.exp(-tt * 30)) * tt) * 0.35
for k in range(int((secs - switch) / (2 * bar)) + 2):            # warm chord pad underneath
    start = switch + k * 2 * bar
    env = np.clip(1 - np.abs((t - start - bar) / (bar * 1.2)), 0, 1)
    for f in prog[k % 4]:
        up += env * np.sin(np.pi * f * t) * 0.035

x = np.clip((t - switch + 1.5) / 3.0, 0, 1)                         # 3 s crossfade
sig = sombre * (1 - x) * 0.8 + up * x
sig *= np.clip(t / 3, 0, 1) * np.clip((secs - t) / 4, 0, 1)
sig = sig / np.abs(sig).max() * 0.5
sf.write(out, np.stack([sig, sig], axis=1).astype(np.float32), SR)
