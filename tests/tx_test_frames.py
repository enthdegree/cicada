# Play test pulses through the speakers
import time, numpy as np, sounddevice as sd
from datetime import datetime
from imprint import payload

def test_chars():
	ch = datetime.now().strftime("%A %B %d, %Y %I:%M:%S %p")
	ch = ch + ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' * int(payload.k)
	return ch.encode("ascii")[:int(payload.k/8)]

while True:
	v_chars = test_chars()
	print(v_chars.decode('utf-8'))
	v_bits = payload.make_frame_bits(v_chars)
	v_sam = payload.make_frame_samples(v_bits)
	sd.play(v_sam, int(payload.wf.fs_Hz)); 
	sd.wait(); 
	time.sleep(0.5)
