#!/usr/bin/env python3
import sys, csv, numpy as np
from fsk.demodulate import FSKDemodulator, FSKDemodulatorParameters
import frame

demod_params = FSKDemodulatorParameters(
	pulse_frac=32,
	frame_search_win = 1.2,
	frame_search_win_step = 0.4,
	symbols_per_frame=frame.k
	)
demod = FSKDemodulator(cfg=demod_params, wf=frame.wf)

def load_wav(path):
	try:
		import soundfile as sf
		x, fs = sf.read(path, dtype="float32", always_2d=False)
	except Exception:
		from scipy.io import wavfile
		fs, x = wavfile.read(path)
		x = x.astype(np.float32) / (np.iinfo(x.dtype).max if np.issubdtype(x.dtype, np.integer) else 1.0)
	if x.ndim > 1: x = x.mean(axis=1)
	return x.astype(np.float32, copy=False), int(fs)

def bits_ascii(b):
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	pb = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	if pad: pb = pb[:-1]
	return pb.decode("ascii", errors="replace")

def main():
	in_wav = sys.argv[1] if len(sys.argv) > 1 else "output.wav"
	out_csv = sys.argv[2] if len(sys.argv) > 2 else "frames.csv"
	x, fs = load_wav(in_wav)

	frames = demod.frame_search(x)
	
	with open(out_csv, "w", newline="") as f:
		w = csv.writer(f)
		w.writerow(["frame_start_sample_idx","ascii"])
		for iframe in range(len(frames[0])):
			print(f'Decoding frame {iframe+1} of {len(frames[0])}')
			print(f'Location: {frames[0][iframe].start_sample} ({frames[0][iframe].start_sample/frame.wf.fs_Hz} s)')
			fr = frames[0][iframe]			
			ll = fr.log_likelihood[0,:].ravel()-fr.log_likelihood[1,:].ravel() 
			bits_dec = ll < 0 # decoder goes here 
			ch_dec = "".join("1" if (b>0) else "0" for b in bits_dec) 
			ch_msg = bits_ascii(bits_dec) 
			print(ch_msg)
			w.writerow([fr.start_sample, ch_msg])

if __name__ == "__main__":
	main()
