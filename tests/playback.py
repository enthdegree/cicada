# Play dummy pulses through the speakers
import time, numpy as np, sounddevice as sd
from datetime import datetime
import frame

def payload_chars():
	ch = datetime.now().strftime("%A %B %d, %Y %I:%M:%S %p")
	ch = ch + ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' * int(frame.k)
	return ch.encode("ascii")[:int(frame.k/8)]

while True:
	v_chars = payload_chars()
	print(v_chars.decode('utf-8'))
	v_bits = frame.make_frame_bits(v_chars)
	v_sam = frame.make_frame_samples(v_bits)
	sd.play(v_sam, int(frame.wf.fs_Hz)); 
	sd.wait(); 
	time.sleep(0.5)
