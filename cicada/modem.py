"""Utilities to convert byte data to/from audio samples.
Modem is the ugly glue that abstracts modulation, demodulation, FEC, etc.
Includes a default 1024-bit LDPC code construction.
"""
import pyldpc, numpy as np
from .fsk.waveform import FSKWaveform
from .fsk.demodulator import FSKDemodulator
from dataclasses import dataclass
import warnings

def no_fec_encoder(v_bits): return v_bits
def no_fec_decoder(bit_llrs): return np.array([0 if llr >= 0 else 1 for llr in bit_llrs], dtype=np.uint8)

# Default LDPC code construction
n_code_sym_per_frame = 1024 # "N" for the binary LDPC code defined below
n_data_bits_per_frame = 513 # "K" for the binary LDPC code defined below
d_v = 2 # variable node degree
d_c = 4 # check node degree
np.random.seed(0)
ldpc_H, ldpc_G = pyldpc.make_ldpc(n_code_sym_per_frame, d_v, d_c, systematic=True, sparse=True)
def ldpc_enc_bits(b, ldpc_G=ldpc_G):
    if b.size > n_data_bits_per_frame: warnings.warn(f"Input has {b.size} bits; cropping to {n_data_bits_per_frame} bits.")
    b = np.pad(b[:n_data_bits_per_frame], (0, max(0, n_data_bits_per_frame - b.size)), 'constant')
    return (ldpc_G @ b) % 2 
def ldpc_dec_bit_llrs(bit_llrs, ldpc_H=ldpc_H): # bit_llrs ~ log(P(b=0)/P(b=1))
	dec_bits = pyldpc.decode(ldpc_H, bit_llrs, snr=0, maxiter=300)
	return dec_bits[:n_data_bits_per_frame]

@dataclass
class Modem:
    bit_modulator: callable
    bit_error_correction_encoder: callable = no_fec_encoder
    bit_error_correction_decoder: callable = None
    demodulator: FSKDemodulator = None
    
    def __init__(self, wf: FSKWaveform, demodulator: FSKDemodulator = None, use_ldpc: bool = True):
        self.bit_modulator = wf.modulate_frame
        self.demodulator = demodulator
        if use_ldpc and demodulator is not None:
            if not (demodulator.symbols_per_frame * demodulator.wf.bits_per_symbol) == n_code_sym_per_frame:
                raise ValueError("Default LDPC construction does not match FSKDemodulator's symbols_per_frame and waveform's n_bits_per_symbol.")
            
        self.bit_error_correction_encoder = ldpc_enc_bits if use_ldpc else no_fec_encoder
        self.bit_error_correction_decoder = ldpc_dec_bit_llrs if use_ldpc else no_fec_decoder

    def modulate_bytes(self, v_data_bytes): 
        buf = np.frombuffer(v_data_bytes, dtype=np.uint8)
        v_data_bits = np.unpackbits(buf)
        v_enc_bits = self.bit_error_correction_encoder(v_data_bits)
        return self.bit_modulator(v_enc_bits).astype(np.float32)

    def recover_bytes(self, v_samples): # Actually this was last seen working using mP[0,:] - mP[1,:] instead of bit_llrs. bizarre
        l_dr = self.demodulator.frame_search(v_samples)[0]
        l_frame_bytes = []
        l_start_idxs = []
        for dr in l_dr:
            v_data_bits = self.bit_error_correction_decoder(dr.bit_llrs)
            n_pad = (-len(v_data_bits)) % 8
            if n_pad > 0: v_data_bits = np.concatenate([v_data_bits, np.zeros(n_pad, dtype=np.uint8)])
            buf = np.packbits(v_data_bits)
            l_frame_bytes.append(buf.tobytes())
            l_start_idxs.append(dr.start_idx)
        return l_frame_bytes, l_start_idxs