#!/usr/bin/env python3
from functools import partial
import numpy as np
import sounddevice as sd
import queue
import threading
import blst
from faster_whisper import WhisperModel
from cicada import payload, speech
from cicada.fsk.demodulator import FSKDemodulatorParameters, FSKDemodulator
from cicada.fsk.waveform import FSKParameters, FSKWaveform, default_mod_table

debug = True

# BLS key and message properties
header_message = "q3q.net"
bls_pubkey_file = "./bls_pubkey.bin"
bls_privkey_file = "./bls_privkey.bin"

# Whisper speech model settings
model_size = "medium.en"
window_sec = 10.0
overlap_sec = 5.0
mic_blocksize_sam = 1024

# Waveform settings
n_code_sym_per_frame = 1024 # must match cicada.modem default LDPC code
wf_params = FSKParameters(
	symbol_rate_Hz=(44100.0/128.0),
	hop_factor=63,
	mod_table_fn=partial(default_mod_table, pattern=16),
)
demod_params = FSKDemodulatorParameters(
	symbols_per_frame=n_code_sym_per_frame, # number of coded symbols per frame
	frame_search_win=1.2, # search window length in # of frames
	frame_search_win_step=0.3, # search window shift length in # of frames
	pulse_frac=8, # fraction of a pulse to use in pulse search
	plot=True) 

############################################################

# Construct Cicada modem
wf = FSKWaveform(wf_params)
demod = FSKDemodulator(cfg=demod_params, wf=wf)
modem = payload.Modem(
	bit_modulator=wf,
	demodulator=demod,
	use_ldpc=True)

# Load speech model
model = WhisperModel(model_size, compute_type="float32")

# Load BLS keys
with open(bls_privkey_file, "rb") as f: bls_privkey_bytes = f.read()
with open(bls_pubkey_file, "rb") as f: bls_pubkey_bytes = f.read()
bls_privkey = blst.SecretKey()
bls_privkey.from_bendian(bls_privkey_bytes)
bls_pubkey = blst.P2_Affine(bls_pubkey_bytes)

# Spin up worker threads
q_mic = queue.Queue()
q_tokens = queue.Queue()
t_mic = threading.Thread(
	target=speech.mic_worker,
	args=(q_mic,),
	kwargs={'mic_blocksize_sam': mic_blocksize_sam},
	daemon=True)
t_transcriber = threading.Thread(
	target=speech.audio_transcript_worker,
	args=(speech.model, q_mic, q_tokens),
	kwargs={'window_sec': window_sec, 'overlap_sec': overlap_sec, 'debug': debug},
	daemon=True)
t_mic.start()
t_transcriber.start()

while True: # Go collecting text, forming it into frames and playing it back
	l_tokens = None
	try: # Get the latest window of text
		while True: l_tokens = q_tokens.get_nowait()
	except queue.Empty: pass
	if l_tokens is None: l_tokens = q_tokens.get() 
	transcript_str = ""
	for tok in l_tokens: transcript_str += " " + tok.text
	print(transcript_str)

	# Form this frame from the token list and transmit it
	pl = payload.SignaturePayload.from_token_list(
		tokens=l_tokens, 
		header_message=header_message, 
		bls_privkey=bls_privkey, 
		bls_pubkey_bytes=bls_pubkey_bytes)
	pl_bytes = pl.to_bytes()
	frame_samples = modem.modulate_bytes(pl_bytes) 
	sd.play(frame_samples, int(payload.wf.fs_Hz)); 
	sd.wait()
