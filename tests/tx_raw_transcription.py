#!/usr/bin/env python3
import numpy as np
import sounddevice as sd
import queue
import threading
from imprint import frame_builder, speech

q_mic = queue.Queue()
q_text = queue.Queue()
t_mic = threading.Thread(
	target=speech.mic_producer, 
	args=(q_mic,), 
	daemon=True)
t_transcriber = threading.Thread(
	target=speech.transcribe_audio_loop, 
	args=(speech.model, q_mic, q_text, False),
	daemon=True)
t_mic.start()
t_transcriber.start()

# Go collecting text, forming it into frames and playing it back
while True:
	l_words = None
	try: # Get the latest window of text
		while True: l_words = q_text.get_nowait()
	except queue.Empty: pass
	if l_words is None: l_words = q_text.get() 
	frame_str = ""
	for word in l_words: frame_str += " " + word[0]
	print(frame_str)

	# Form and transmit this frame
	frame_ch = frame_str.encode("ascii")
	frame_bits = frame_builder.make_frame_bits(frame_ch)
	frame_samples = frame_builder.make_frame_samples(frame_bits) 
	sd.play(frame_samples, int(frame_builder.wf.fs_Hz)); 
	sd.wait()

