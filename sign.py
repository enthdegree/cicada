#!/usr/bin/env python3
import numpy as np
import sounddevice as sd
import queue
import threading
import blst
from imprint import payload, speech

q_mic = queue.Queue()
q_tokens = queue.Queue()
t_mic = threading.Thread(
	target=speech.mic_producer, 
	args=(q_mic,), 
	daemon=True)
t_transcriber = threading.Thread(
	target=speech.transcribe_audio_loop, 
	args=(speech.model, q_mic, q_tokens, False),
	daemon=True)
t_mic.start()
t_transcriber.start()

# BLS key and message properties
header_message = "q3q.net"
bls_pubkey_file = "./bls_pubkey.bin"
bls_privkey_file = "./bls_privkey.bin"
with open(bls_privkey_file, "rb") as f: bls_privkey_bytes = f.read()
with open(bls_pubkey_file, "rb") as f: bls_pubkey_bytes = f.read()
bls_privkey = blst.SecretKey()
bls_privkey.from_bendian(bls_privkey_bytes)
bls_pubkey = blst.P2_Affine(bls_pubkey_bytes)

# Go collecting text, forming it into frames and playing it back
while True:
	l_tokens = None
	try: # Get the latest window of text
		while True: l_tokens = q_tokens.get_nowait()
	except queue.Empty: pass
	if l_tokens is None: l_tokens = q_tokens.get() 
	transcript_str = ""
	for tok in l_tokens: transcript_str += " " + tok.text
	print(transcript_str)

	# Form and transmit this frame
	pl = payload.make_payload(l_tokens, header_message, bls_privkey, bls_pubkey_bytes)
	pl_ch = payload.payload_to_ch(pl)
	frame_samples = payload.modulate_bytes(pl_ch) 
	sd.play(frame_samples, int(payload.wf.fs_Hz)); 
	sd.wait()

