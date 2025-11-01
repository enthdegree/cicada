#!/usr/bin/env python3
import time, numpy as np, sounddevice as sd
from imprint import frame_builder, speech
import queue
import threading

q_mic = queue.Queue()
q_text = queue.Queue()
t_mic = threading.Thread(
	target=speech.mic_producer, 
	args=(speech.sample_rate_Hz, speech.chunk_len_sam, q_mic), 
	daemon=True)
t_transcriber = threading.Thread(
	target=speech.transcribe_audio_loop, 
	args=(speech.model, speech.sample_rate_Hz, q_mic, q_text, False),
	daemon=True)
t_mic.start()
t_transcriber.start()

# Go collecting text, forming it into frames and playing it back
while True:
	frame_ch = None
	try: 
		while True: frame_ch = q_text.get_nowait()
	except queue.Empty: pass
	if frame_ch is None: frame_ch = q_text.get() 
	print(frame_ch.decode('utf-8'))
	frame_bits = frame_builder.make_frame_bits(frame_ch)
	frame_samples = frame_builder.make_frame_samples(frame_bits) 
	sd.play(frame_samples, int(frame_builder.wf.fs_Hz)); 
	sd.wait()

