# Frame assembly helpers
import time, numpy as np
from datetime import datetime
from functools import partial
from fsk.waveform import FSKWaveform, FSKParameters, default_mod_table

k = 1026
wfp = FSKParameters(
	symbol_rate_Hz=344.53125,
	hop_factor=16,
	mod_table_fn=partial(default_mod_table, pattern=7),
)
wf = FSKWaveform(wfp)

def bits_from_ascii(b): 
	return np.unpackbits(np.frombuffer(b, dtype=np.uint8), bitorder="big")
def make_frame_bits(txt, k=k):
	txt = ('ASDFGHJKLZXCVBNM asdfghjklzxcvbnm!!>?@ ' * k + txt)[-int(k/8):].encode("ascii")
	n_msg_bits = min(len(txt)*8, k); 
	msg_bits = np.zeros(k, np.uint8)
	msg_bits[:n_msg_bits] = bits_from_ascii(txt)[:n_msg_bits]
	return msg_bits

def make_frame_samples(frame_bits):
	return wf.modulate_frame(frame_bits).astype(np.float32)
