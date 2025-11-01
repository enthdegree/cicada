# Frame assembly and modulation routines

import time, numpy as np
from datetime import datetime
from functools import partial
from imprint.fsk.waveform import FSKWaveform, FSKParameters, default_mod_table
from imprint.fsk.demodulate import FSKDemodulator, FSKDemodulatorParameters

k = 1026
wf_params = FSKParameters(
	symbol_rate_Hz=344.53125,
	hop_factor=63,
	mod_table_fn=partial(default_mod_table, pattern=16),
)
wf = FSKWaveform(wf_params)
demod_params = FSKDemodulatorParameters(
	symbols_per_frame=1026, # number of coded symbols per frame
	frame_search_win=1.2, # search window length in # of frames
	frame_search_win_step=0.3, # search window shift length in # of frames
	pulse_frac=8, # fraction of a pulse to use in pulse search
	plot=True) 
demod = FSKDemodulator(cfg=demod_params, wf=wf)

def bits_from_ascii(b): 
	return np.unpackbits(np.frombuffer(b, dtype=np.uint8), bitorder="big")

def make_frame_bits(v_chars, k=k):
	v_chars = (str(v_chars.decode('utf-8')) + ' ' + 'ASDFGHJKLZXCVBNMqwertyuiop'*10).encode('ascii')
	n_msg_bits = min(len(v_chars)*8, k); 
	v_bits = np.zeros(k, np.uint8)
	v_bits[:n_msg_bits] = bits_from_ascii(v_chars)[:n_msg_bits]
	return v_bits

def make_frame_samples(frame_bits):
	return wf.modulate_frame(frame_bits).astype(np.float32)
