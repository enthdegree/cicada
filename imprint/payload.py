# Routines for packing/unpacking payloads 
import time, base64, numpy as np
from datetime import datetime
from functools import partial
from imprint.fsk.waveform import FSKWaveform, FSKParameters, default_mod_table
from imprint.fsk.demodulate import FSKDemodulator, FSKDemodulatorParameters
import pyldpc
from dataclasses import dataclass

n = 1024
k = 513
wf_params = FSKParameters(
	symbol_rate_Hz=(44100.0/128.0),
	hop_factor=63,
	mod_table_fn=partial(default_mod_table, pattern=16),
)
wf = FSKWaveform(wf_params)
demod_params = FSKDemodulatorParameters(
	symbols_per_frame=n, # number of coded symbols per frame
	frame_search_win=1.2, # search window length in # of frames
	frame_search_win_step=0.3, # search window shift length in # of frames
	pulse_frac=8, # fraction of a pulse to use in pulse search
	plot=True) 
demod = FSKDemodulator(cfg=demod_params, wf=wf)

# LDPC params
d_v = 2 # variable node degree
d_c = 4 # check node degree
np.random.seed(0)
ldpc_H, ldpc_G = pyldpc.make_ldpc(n, d_v, d_c, systematic=True, sparse=True)

def enc_bits(b): 
	return (ldpc_G @ b) % 2

def dec_ll(ll): # ll ~ log(P(b=0)/P(b=1))
	dec = pyldpc.decode(ldpc_H, ll, snr=0, maxiter=100)
	return dec[:k]

def bits_from_ascii(b): 
	return np.unpackbits(np.frombuffer(b, dtype=np.uint8), bitorder="big")

def bits_to_base64(b):
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	pb = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	return base64.b64encode(pb).decode("ascii")

def bits_to_ascii(b):
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	pb = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	return pb.decode("ascii", errors="replace")

def chars_to_frame_bits(v_chars, k=k):
	v_chars = (str(v_chars.decode('utf-8')) + ' ' + 'ASDFGHJKLZXCVBNMqwertyuiop'*10).encode('ascii')
	n_msg_bits = min(len(v_chars)*8, k); 
	v_bits = np.zeros(k, np.uint8)
	v_bits[:n_msg_bits] = bits_from_ascii(v_chars)[:n_msg_bits]
	v_frame_bits = enc_bits(v_bits)
	return v_frame_bits

def modulate_frame(frame_bits): 
	return wf.modulate_frame(frame_bits).astype(np.float32)
