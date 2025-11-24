"""Utilities to convert byte data to/from audio samples.
Modem is the glue that abstracts modulation, demodulation, FEC, etc.
Includes a default 1024-bit LDPC code construction.
"""
from __future__ import annotations

import warnings
import numpy as np
import pyldpc

from .fsk.waveform import FSKWaveform
from .fsk.demodulator import FSKDemodulator

def no_fec_encoder(v_bits): return v_bits
def no_fec_decoder(bit_llrs): return np.array([0 if llr >= 0 else 1 for llr in bit_llrs], dtype=np.uint8)

# Default LDPC code construction
n_ldpc_code_sym_per_frame = 1024 # "N" for the binary LDPC code defined below
n_ldpc_data_bits_per_frame = 513 # "K" for the binary LDPC code defined below
d_v = 2 # variable node degree
d_c = 4 # check node degree
np.random.seed(0)
ldpc_H, ldpc_G = pyldpc.make_ldpc(n_ldpc_code_sym_per_frame, d_v, d_c, systematic=True, sparse=True)
default_bit_mask = np.random.randint(0, 2, size=n_ldpc_code_sym_per_frame, dtype=np.uint8)
def ldpc_enc_bits(b, ldpc_G=ldpc_G):
	if b.size != n_ldpc_data_bits_per_frame:
		raise ValueError(f"LDPC encoder expects {n_ldpc_data_bits_per_frame} bits (got {b.size}).")
	return (ldpc_G @ b) % 2

def ldpc_dec_bit_llrs(bit_llrs, ldpc_H=ldpc_H):
	dec_bits = pyldpc.decode(ldpc_H, bit_llrs, snr=0, maxiter=300)
	return dec_bits[:n_ldpc_data_bits_per_frame]

class Modem:
	def __init__(self, wf: FSKWaveform, demodulator: FSKDemodulator = None, discard_duplicate_frames: bool = True, use_ldpc: bool = True, use_bit_mask: bool = True):
		self.wf = wf
		self.bit_modulator = wf.modulate_frame
		self.demodulator = demodulator
		self.use_bit_mask = use_bit_mask
		self.bit_mask = default_bit_mask.copy() if use_bit_mask else None
		self.discard_duplicate_frames = discard_duplicate_frames

		self.data_bits_per_frame = min(n_ldpc_data_bits_per_frame, wf.symbols_per_frame * wf.bits_per_symbol)
		self.bytes_per_frame = self.data_bits_per_frame // 8

		if use_ldpc and demodulator is not None: # Ensure demodulator's compatibility with default LDPC construction
			if (not (wf.symbols_per_frame == n_ldpc_code_sym_per_frame)) or (not (demodulator.wf.bits_per_symbol == 1)):
				raise ValueError("Modem was constructed to use the default binary LDPC construction, but the waveform objects are incompatible (demod.symbols_per_frame is bad or wf.bits_per_symbol is bad).")
		self.bit_error_correction_encoder = ldpc_enc_bits if use_ldpc else no_fec_encoder
		self.bit_error_correction_decoder = ldpc_dec_bit_llrs if use_ldpc else no_fec_decoder

	def modulate_bytes(self, v_data_bytes):
		buf = np.frombuffer(v_data_bytes, dtype=np.uint8)
		v_data_bits = np.unpackbits(buf)
		max_bits = self.data_bits_per_frame
		if v_data_bits.size > max_bits:
			warnings.warn(
				f"Truncating input ({v_data_bits.size} bits / {v_data_bits.size/8:.1f} bytes) to {max_bits} bits (~{max_bits//8} bytes).",
				stacklevel=2,
			)
			v_data_bits = v_data_bits[:max_bits]
		if v_data_bits.size < max_bits:
			v_data_bits = np.pad(v_data_bits, (0, max_bits - v_data_bits.size), constant_values=0)
		if self.bit_mask is not None:
			v_data_bits = self.mask_bits(v_data_bits)
		v_enc_bits = self.bit_error_correction_encoder(v_data_bits)
		return self.bit_modulator(v_enc_bits).astype(np.float32)

	def recover_bytes(self, v_samples):
		l_dr = self.demodulator.frame_search(v_samples)[0]
		l_frame_bytes = []
		l_start_idxs = []
		for dr in l_dr:
			v_data_bits = self.bit_error_correction_decoder(dr.bit_llrs)
			v_data_bits = v_data_bits[:self.data_bits_per_frame]
			if self.bit_mask is not None:
				v_data_bits = self.unmask_bits(v_data_bits)
			n_pad = (-len(v_data_bits)) % 8
			if n_pad > 0:
				v_data_bits = np.concatenate([v_data_bits, np.zeros(n_pad, dtype=np.uint8)])
			fb = np.packbits(v_data_bits).tobytes()
			if self.discard_duplicate_frames and fb in l_frame_bytes: continue
			l_frame_bytes.append(fb)
			l_start_idxs.append(dr.start_idx)
		return l_frame_bytes, l_start_idxs

	def mask_bits(self, v_bits):
		if self.bit_mask is None:
			return v_bits
		n = min(len(v_bits), len(self.bit_mask))
		v_bits_masked = v_bits.copy()
		v_bits_masked[:n] = v_bits[:n] ^ self.bit_mask[:n]
		return v_bits_masked

	def unmask_bits(self, v_bits): return self.mask_bits(v_bits)
