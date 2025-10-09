# scripts/demod_decode.py
from __future__ import annotations
import numpy as np
import csv, os, sys
from fsk.waveform import FSKWaveform, FSKParams
from ldpc.ldpc import Decoder, N

def main(in_wav: str, out_csv: str,
         M: int=1, P: int=160, Nrep: int=2, F: int=69, fs:int=44100,
         frame_bits: int=1024, win_frames: float=1.5, hop_frames: float=0.5, coarse_step: int|None=None):
    import soundfile as sf
    x, fs_read = sf.read(in_wav)
    if x.ndim == 2: x = x.mean(axis=1)
    if fs_read != fs:
        print(f"[warn] WAV fs={fs_read} != requested fs={fs}; continuing.", file=sys.stderr)
    wf = FSKWaveform(FSKParams(M=M, P=P, N=Nrep, F=F, fs=fs))
    frames = wf.search_and_demodulate(x, frame_bits=frame_bits, win_frames=win_frames, hop_frames=hop_frames, coarse_step=coarse_step)
    dec = Decoder(alpha=0.8)
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)) or '.', exist_ok=True)
    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['start_sample','threshold','demod_bits','decoded_bits'])
        for fr in frames:
            bits_str = fr['bits']
            if len(bits_str) < N:
                bits_str = bits_str + '0'*(N-len(bits_str))
            llr = fr['llr']
            if llr.shape[0] < N:
                llr = np.pad(llr, (0, N-llr.shape[0]), mode='constant', constant_values=0.0)
            hard, iters, ok = dec.decode(llr, max_iters=60)
            decoded_bits = ''.join(str(int(b)) for b in hard.tolist())
            w.writerow([fr['start'], f"{fr['threshold']:.6f}", bits_str[:N], decoded_bits])
    print(f"Wrote {len(frames)} rows to {out_csv}")

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description="Demodulate and LDPC-decode FSK frames from a WAV file.")
    ap.add_argument('--in', dest='in_wav', default='output.wav', help='Input WAV (default: output.wav)')
    ap.add_argument('--out', dest='out_csv', default='frames.csv', help='Output CSV (default: frames.csv)')
    ap.add_argument('--M', type=int, default=1)
    ap.add_argument('--P', type=int, default=160)
    ap.add_argument('--N', dest='Nrep', type=int, default=2)
    ap.add_argument('--F', type=int, default=69)
    ap.add_argument('--fs', type=int, default=44100)
    ap.add_argument('--frame_bits', type=int, default=1024)
    ap.add_argument('--win_frames', type=float, default=1.5)
    ap.add_argument('--hop_frames', type=float, default=0.5)
    ap.add_argument('--coarse_step', type=int, default=None)
    args = ap.parse_args()
    main(args.in_wav, args.out_csv, args.M, args.P, args.Nrep, args.F, args.fs, args.frame_bits, args.win_frames, args.hop_frames, args.coarse_step)
