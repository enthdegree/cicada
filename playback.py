#!/usr/bin/env python3
import time, numpy as np, sounddevice as sd
from datetime import datetime
from ldpc.ldpc import Encoder, K
from fsk.waveform import FSKWaveform
def bits_from_ascii(b): return np.unpackbits(np.frombuffer(b, dtype=np.uint8), bitorder="big")
def payload():
    u = np.zeros(K, np.uint8); ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S").encode("ascii")
    n = min(len(ts)*8, K); u[:n] = bits_from_ascii(ts)[:n]; return u
wf, enc = FSKWaveform(), Encoder()
while True:
    cw = enc.encode(payload())
    x = wf.modulate_frame(cw).astype(np.float32)
    sd.play(x, int(wf.fs_Hz)); sd.wait(); time.sleep(0.1)
