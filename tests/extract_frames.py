# Pull frames out of output.wav and dump them to frames.csv
import sys, csv, numpy as np
from imprint import frame_builder 

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

	frames = frame_builder.demod.frame_search(x)
	
	with open(out_csv, "w", newline="") as f:
		w = csv.writer(f)
		w.writerow(["pulse_map_idx","ascii"])
		for iframe in range(len(frames[0])):
			frame_start_sam = frames[0][iframe].pulse_map_idx*frame_builder.demod.pulse_frac
			frame_start_sec = frame_start_sam/frame_builder.wf.fs_Hz
			print(f'Decoding frame {iframe+1} of {len(frames[0])}')
			print(f'Location: {frame_start_sam} ({frame_start_sec} s)')
			fr = frames[0][iframe]			
			ll = fr.log_likelihood[0,:].ravel()-fr.log_likelihood[1,:].ravel() 
			bits_dec = ll < 0 # decoder goes here 
			ch_dec = "".join("1" if (b>0) else "0" for b in bits_dec) 
			ch_msg = bits_ascii(bits_dec) 
			print(ch_msg)
			w.writerow([fr.pulse_map_idx, ch_msg])

if __name__ == "__main__":
	main()
