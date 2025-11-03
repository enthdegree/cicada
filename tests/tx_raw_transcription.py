#!/usr/bin/env python3
import numpy as np
import sounddevice as sd
import queue
import threading
from imprint import payload, speech

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
	transcript_str = ""
	for word in l_words: transcript_str += " " + word[0]
	print(transcript_str)

	# Form and transmit this frame
	transcript_ch = transcript_str.encode("ascii")
	frame_bits = payload.make_frame_bits(transcript_ch)
	frame_samples = payload.make_frame_samples(frame_bits) 
	sd.play(frame_samples, int(payload.wf.fs_Hz)); 
	sd.wait()

