# Play dummy pulses through the speakers
import time, numpy as np, sounddevice as sd
from datetime import datetime
from imprint import frame_builder

def payload_chars():
	ch = datetime.now().strftime("%A %B %d, %Y %I:%M:%S %p")
	ch = ch + ' ABCDEFGHIJKLMNOPQRSTUVWXYZ' * int(frame_builder.k)
	return ch.encode("ascii")[:int(frame_builder.k/8)]

while True:
	v_chars = payload_chars()
	print(v_chars.decode('utf-8'))
	v_bits = frame_builder.make_frame_bits(v_chars)
	v_sam = frame_builder.make_frame_samples(v_bits)
	sd.play(v_sam, int(frame_builder.wf.fs_Hz)); 
	sd.wait(); 
	time.sleep(0.5)
