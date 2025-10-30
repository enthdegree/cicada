#!/usr/bin/env python3
import numpy as np
import wave
import struct
import time
from datetime import datetime

dur_s = 10.0
inter_s = 0.5
out_path = "output.wav"

# Wf definition
from fsk.waveform import FSKWaveform, FSKParameters, default_mod_table
from functools import partial

wfp = FSKParameters(
	symbol_rate_Hz=344.53125,
	hop_factor=32,
	mod_table_fn=partial(default_mod_table, pattern=11),
)
wf = FSKWaveform(wfp)

def bits_from_ascii(b): return np.unpackbits(np.frombuffer(b, dtype=np.uint8), bitorder="big")
def payload():
	str_msg = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	str_msg = (str_msg + ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' * int((1026/8 - len(str_msg))))[:int(1026/8)].encode("ascii")
	print(str_msg)
	n_msg_bits = min(len(str_msg)*8, 1026); 
	msg_bits = np.zeros(1026, np.uint8)
	msg_bits[:n_msg_bits] = bits_from_ascii(str_msg)[:n_msg_bits]
	return msg_bits

def main():
	fs = int(wf.fs_Hz)
	total_samples = int(fs * dur_s)
	out = []
	t0 = time.time()
	while sum(len(x) for x in out) <= total_samples:
		pl = payload()
		sig = wf.modulate_frame(pl).astype(np.float32)
		sig = np.pad(sig, pad_width=int(np.ceil(fs*inter_s)), mode='constant', constant_values=0)
		out.append(sig)
	out.append(np.zeros(int(np.ceil(8*fs*inter_s))))
	y = np.concatenate(out)
	
	# write 16-bit PCM
	with wave.open(out_path, "wb") as w:
		w.setnchannels(1)
		w.setsampwidth(2)  # 16-bit
		w.setframerate(fs)
		for v in y:
			w.writeframesraw(struct.pack("<h", int(v * 32767.0)))

if __name__ == "__main__":
	main()
