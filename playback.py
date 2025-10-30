#!/usr/bin/env python3
import time, numpy as np, sounddevice as sd
from datetime import datetime
from functools import partial
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
	str_msg = datetime.now().strftime("%A %B %d, %Y %I:%M:%S %p")
	str_msg = (str_msg + ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' * int((1026/8 - len(str_msg))))[:int(1026/8)].encode("ascii")
	print(str_msg)
	n_msg_bits = min(len(str_msg)*8, 1026); 
	msg_bits = np.zeros(1026, np.uint8)
	msg_bits[:n_msg_bits] = bits_from_ascii(str_msg)[:n_msg_bits]
	return msg_bits

while True:
	pl = payload()
	pl_mod = wf.modulate_frame(pl).astype(np.float32)
	sd.play(pl_mod, int(wf.fs_Hz)); 
	sd.wait(); 
	time.sleep(0.5)
