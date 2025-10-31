#!/usr/bin/env python3
import time, numpy as np, sounddevice as sd
import frame, speech
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
	try: while True: frame_ch = q.get_nowait()
	except queue.Empty: pass
	if frame_ch is None: txt = q.get() 

	frame_bits = frame.make_frame_bits(frame_ch)
	frame_samples = frame.make_frame_samples(frame_bits) 
	sd.play(frame_samples, int(frame.wf.fs_Hz)); 
	sd.wait()

