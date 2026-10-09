"""Synthesize a soft, slow ambient pad (no samples, no licensing issues).

    python pad.py <seconds> <out.wav>
"""
import sys

import numpy as np
import soundfile as sf

secs, out = float(sys.argv[1]), sys.argv[2]
SR = 48000
t = np.arange(int(secs * SR)) / SR
# A minor -> F major -> C major -> G major, 8 s per chord, gentle fades.
chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [130.81, 164.81, 196.0], [196.0, 246.94, 293.66]]
sig = np.zeros_like(t)
seg = 8.0
for k in range(int(np.ceil(secs / seg)) + 1):
    start = k * seg
    env = np.clip(1 - np.abs((t - start - seg / 2) / (seg * 0.75)), 0, 1) ** 1.5
    for f in chords[k % 4]:
        for detune in (-0.6, 0.6):
            sig += env * np.sin(2 * np.pi * (f + detune) * t) * 0.05
        sig += env * np.sin(2 * np.pi * f / 2 * t) * 0.04
sig *= np.clip(t / 3, 0, 1) * np.clip((secs - t) / 4, 0, 1)
sig = sig / np.abs(sig).max() * 0.5
sf.write(out, np.stack([sig, sig], axis=1).astype(np.float32), SR)
