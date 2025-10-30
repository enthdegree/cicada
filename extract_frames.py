#!/usr/bin/env python3
import sys, csv, pyldpc, numpy as np
from fsk.demodulate import FSKDemodulator

ldpc_dec = Decoder()

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

def bits_str(bits):
	b = np.asarray(bits, dtype=np.uint8).ravel(); 
	b[b!=0]=1
	return "".join("1" if v else "0" for v in b.tolist())

def bits_ascii(bitstr):
	b = np.fromiter((1 if c=="1" else 0 for c in bitstr), dtype=np.uint8)
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	by = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	return by.decode("ascii", errors="replace")

def main():
	in_wav = sys.argv[1] if len(sys.argv) > 1 else "output.wav"
	out_csv = sys.argv[2] if len(sys.argv) > 2 else "frames.csv"
	x, fs = load_wav(in_wav)

	demod = FSKDemodulator()
	frames = demod.frame_search(x)
	
	with open(out_csv, "w", newline="") as f:
		w = csv.writer(f)
		w.writerow(["frame_start_sample_idx","frame_demod","frame_ascii"])
		for iframe in range(len(frames[0])):
			print(f'Decoding frame {iframe} of {len(frames[0])}')
			fr = frames[0][iframe]			
			ll = fr.log_likelihood[1,:].ravel() - fr.log_likelihood[0,:].ravel() 
			bits_dec = ldpc_dec.decode(ll)[0]
			str_dec = "".join("1" if b else "0" for b in bits_dec.tolist()) 
			str_msg = bits_ascii(msg_bits) 
			w.writerow([fr.start_sample, str_dec, str_msg])
			print(msg_bits)
			print(str_msg)

if __name__ == "__main__":
	main()
