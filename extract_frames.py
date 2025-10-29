#!/usr/bin/env python3
import sys, csv, numpy as np

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
	b = np.asarray(bits, dtype=np.uint8).ravel(); b[b!=0]=1
	return "".join("1" if v else "0" for v in b.tolist())

def bits_ascii(bitstr):
	if not bitstr: return ""
	b = np.fromiter((1 if c=="1" else 0 for c in bitstr), dtype=np.uint8)
	pad = (-len(b)) % 8
	if pad: b = np.concatenate([b, np.zeros(pad, np.uint8)])
	by = np.packbits(b.reshape(-1,8), bitorder="big").tobytes()
	return by.decode("ascii", errors="replace")

def main():
	in_wav = sys.argv[1] if len(sys.argv) > 1 else "output.wav"
	out_csv = sys.argv[2] if len(sys.argv) > 2 else "frames.csv"
	x, fs = load_wav(in_wav)

	from fsk.demodulate import FSKDemodulator
	demod = FSKDemodulator()
	frames = demod.frame_search(x)
	
	with open(out_csv, "w", newline="") as f:
		w = csv.writer(f)
		w.writerow(["frame_start_sample_idx","frame_bits","frame_ascii"])
		for fr in frames[0]:
			s = int(fr.start_sample)
			bs = bits_str(fr.syms)
			w.writerow([s, bs, bits_ascii(bs)])

if __name__ == "__main__":
	main()
