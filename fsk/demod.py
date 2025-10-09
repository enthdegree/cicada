# dec_rx.py
# High-level demod utilities built around waveform.FSKWaveform.
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
from .waveform import FSKParams, FSKWaveform

@dataclass
class DemodConfig:
    frame_bits: int = 1024
    win_frames: float = 1.5
    hop_frames: float = 0.5
    coarse_step: int | None = None  # alignment coarse step in samples; default = sps

def demodulate_file_to_csv(wav_path: str, csv_path: str,
                           wf_params: FSKParams = FSKParams(),
                           cfg: DemodConfig = DemodConfig()):
    """
    Load mono WAV, run sliding window demod, and write CSV:
      first column: starting sample index of the frame
      second column: bitstring of length frame_bits
    """
    import soundfile as sf  # lightweight
    x, fs = sf.read(wav_path)
    if x.ndim == 2: x = x.mean(axis=1)
    if fs != wf_params.fs:
        # Allow but warn
        print(f"[warn] WAV fs={fs} does not match params.fs={wf_params.fs}; proceeding anyway.")
    wf = FSKWaveform(wf_params)
    rows = wf.search_and_demodulate(x, frame_bits=cfg.frame_bits,
                                    win_frames=cfg.win_frames, hop_frames=cfg.hop_frames,
                                    coarse_step=cfg.coarse_step)
    import csv, os
    os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        for start, bitstr in rows:
            w.writerow([start, bitstr])
    return len(rows)

# Simple CLI
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('wav', help='input WAV file (mono or stereo)')
    ap.add_argument('csv', help='output CSV path')
    ap.add_argument('--M', type=int, default=1)
    ap.add_argument('--P', type=int, default=160)
    ap.add_argument('--N', type=int, default=2)
    ap.add_argument('--F', type=int, default=69)
    ap.add_argument('--fs', type=int, default=44100)
    ap.add_argument('--win', type=str, default='hann')
    ap.add_argument('--frame_bits', type=int, default=1024)
    ap.add_argument('--win_frames', type=float, default=1.5)
    ap.add_argument('--hop_frames', type=float, default=0.5)
    ap.add_argument('--coarse_step', type=int, default=None)
    args = ap.parse_args()

    params = FSKParams(M=args.M, P=args.P, N=args.N, F=args.F, fs=args.fs, win=args.win)
    cfg = DemodConfig(frame_bits=args.frame_bits, win_frames=args.win_frames,
                      hop_frames=args.hop_frames, coarse_step=args.coarse_step)
    n = demodulate_file_to_csv(args.wav, args.csv, params, cfg)
    print(f"Wrote {n} rows to {args.csv}")
