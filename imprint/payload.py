# Routines for packing/unpacking payloads 
import time, struct, base64, pyldpc, blst, numpy as np
from typing import Iterable
from datetime import datetime
from functools import partial
from dataclasses import dataclass
from imprint.fsk.demodulate import FSKDemodulator, FSKDemodulatorParameters
from imprint.fsk.waveform import FSKWaveform, FSKParameters, default_mod_table

# FSK waveform definition
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

# LDPC code definition
d_v = 2 # variable node degree
d_c = 4 # check node degree
np.random.seed(0)
ldpc_H, ldpc_G = pyldpc.make_ldpc(n, d_v, d_c, systematic=True, sparse=True)

def ldpc_enc_bits(b): # b must have length k
	return (ldpc_G @ b) % 2

def ldpc_dec_ll(ll): # ll ~ log(P(b=0)/P(b=1))
	dec = pyldpc.decode(ldpc_H, ll, snr=0, maxiter=300)
	return dec[:k]

# Payload definition and management
DST = b"BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_"	# domain separation tag

@dataclass 
class Payload: # see DESIGN_NOTES.md # Payload structure
	timestamp: float # bits 0-31; 32-bit big-endian unix timestamp 
	word_count: int # bits 32-39; 8-bit unsigned word count
	header_message: str # bits 40-127; 11-character ascii header message
	bls_signature: bytes # bits 128-511; 384-bit BLS short signature

def make_payload(l_tokens: list, header_message, bls_privkey: blst.SecretKey, bls_pubkey_bytes: bytes, n_header_message_chars: int = 11):
	ts = time.time() 
	wc = len(l_tokens)
	proto_pl = Payload(ts, wc, header_message, bytes(0))
	proto_pl_ch = payload_to_ch(proto_pl)
	sig = sign_tokens(l_tokens, proto_pl_ch[:4+1+n_header_message_chars], bls_privkey, bls_pubkey_bytes)
	return Payload(ts, wc, header_message, sig)

def sign_tokens(l_tokens: Iterable, header_bytes: bytes, bls_privkey: blst.SecretKey, bls_pubkey_bytes: bytes) -> bytes:
	msg = bytearray(header_bytes)
	for tok in l_tokens: msg += (tok.text.encode("utf-8") + b"\x00")
	sig = blst.P1().hash_to(msg, DST, bls_pubkey_bytes) \
		.sign_with(bls_privkey).compress()
	return sig # 48 bytes (384 bits) BLS short signature

def find_payload_in_token_list(pl: Payload, l_tokens: list, bls_pubkey_bytes: bytes, n_header_message_chars: int = 11):
	""" Given a payload and a list l_tokens, try and find (if and) where pl starts in l_tokens. 
	return the index or -1 if no match
	"""
	bls_pubkey = blst.P2_Affine(bls_pubkey_bytes)
	if len(l_tokens) < pl.word_count: return -1 # Not enough words in this list of tokens to compare
	pl_header_len = 4 + 1 + n_header_message_chars
	try: pl_sig = blst.P1_Affine(bytearray(pl.bls_signature))
	except: 
		print('bad pl')
		return -1 
	header_bytes = payload_to_ch(pl, n_header_message_chars=n_header_message_chars)[:pl_header_len]
	for idx in range(len(l_tokens) - pl.word_count + 1):
		msg = bytearray(header_bytes)
		for tok in l_tokens[idx:(idx+pl.word_count)]: msg += (tok.text.encode("utf-8") + b"\x00")
		try: # verify msg against bls_public_key and pl_sig
			ctx = blst.Pairing(True, DST)
			ctx.aggregate(bls_pubkey, pl_sig, msg, bls_pubkey_bytes)
			ctx.commit()
			if ctx.finalverify(): return idx
		except: pass
	return -1

def payload_to_ch(pl: Payload, n_header_message_chars: int=11): 
	timestamp_bytes = struct.pack(">I", int(pl.timestamp))
	word_count_bytes = struct.pack(">B", pl.word_count) 
	message = pl.header_message.encode("ascii", errors="replace")[:n_header_message_chars]
	message_bytes = message.ljust(n_header_message_chars, b"\x00") 
	bls_signature = pl.bls_signature 
	plb = timestamp_bytes + word_count_bytes + message_bytes + bls_signature
	return plb

def ch_to_payload(ch: bytearray, n_header_message_chars: int=11):
	ts_bytes = ch[0:4] 
	timestamp = float(struct.unpack(">I", ts_bytes)[0])

	wc_bytes = ch[4:5]
	word_count = struct.unpack(">B", wc_bytes)[0]

	header_bytes = ch[5:(5+n_header_message_chars)]
	header_message = header_bytes.rstrip(b"\x00").decode("ascii", errors="replace")

	bls_signature_bytes = ch[(5+n_header_message_chars):(5+n_header_message_chars+48)]
	bls_signature = bytes(bls_signature_bytes)

	return Payload(timestamp, word_count, header_message, bls_signature)

def bits_to_ascii(b):
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	pb = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	return pb.decode("ascii", errors="replace")

def bits_from_ascii(b): 
	return np.unpackbits(np.frombuffer(b, dtype=np.uint8), bitorder="big")

def bits_to_base64(b):
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	pb = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	return base64.b64encode(pb).decode("ascii")

# Frame mod and demod
def chars_to_test_frame_bits(v_chars, k=k): # For tests we won't bother with LDPC coding and the signatures 
	v_chars = (str(v_chars.decode('utf-8')) + ' ' + 'ASDFGHJKLZXCVBNMqwertyuiop'*10).encode('ascii')
	n_msg_bits = min(len(v_chars)*8, k); 
	v_bits = np.zeros(k, np.uint8)
	v_bits[:n_msg_bits] = bits_from_ascii(v_chars)[:n_msg_bits]
	v_frame_bits = enc_bits(v_bits)
	return v_frame_bits

def modulate_bits(v_bits): 
	v_enc_bits = ldpc_enc_bits(v_bits)
	return wf.modulate_frame(v_enc_bits).astype(np.float32)

def modulate_bytes(v_bytes, k: int = k):
    buf = np.frombuffer(v_bytes, dtype=np.uint8)
    bits = np.unpackbits(buf)
    if len(bits) > k: raise ValueError(f"Input too long: {len(bits)} bits (max {k})")
    if len(bits) < k: bits = np.pad(bits, (0, k - len(bits)), constant_values=0)
    return modulate_bits(bits)


