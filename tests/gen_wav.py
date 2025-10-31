#!/usr/bin/env python3

# Generate an output.wav with some dummy pulses in it
import numpy as np
import wave
import struct
import time
from datetime import datetime
import frame

dur_s = 10.0
inter_s = 0.5
out_path = "output.wav"

def payload_chars():
	ch = datetime.now().strftime("%A %B %d, %Y %I:%M:%S %p")
	ch = (ch + ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' * int(frame.k/8))[:int(frame.k/8)]
	return ch.encode("ascii")

fs = int(frame.wf.fs_Hz)
total_samples = int(fs * dur_s)
out = []
t0 = time.time()
while sum(len(x) for x in out) <= total_samples:
	v_ch = payload_chars()
	print(v_ch.decode('utf-8'))
	v_bits = frame.make_frame_bits(v_ch)
	v_sam = frame.make_frame_samples(v_bits)
	v_sam = np.pad(v_sam, pad_width=int(np.ceil(fs*inter_s)), mode='constant', constant_values=0)
	out.append(v_sam)
out.append(np.zeros(int(np.ceil(8*fs*inter_s))))
y = np.concatenate(out)

with wave.open(out_path, "wb") as w:
	w.setnchannels(1)
	w.setsampwidth(2)  # 16-bit
	w.setframerate(fs)
	for v in y:
		w.writeframesraw(struct.pack("<h", int(v * 32767.0)))

