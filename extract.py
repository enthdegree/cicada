#!/usr/bin/env python3
"""Extract payload frames from a recording."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

from cicada import payload, interface

def load_audio(path: Path) -> tuple[np.ndarray, int]:
	samples, fs = sf.read(path, dtype="float32", always_2d=False)
	if samples.ndim > 1:
		samples = samples.mean(axis=1)
	return samples.astype(np.float32, copy=False), int(fs)

def extract_payloads(args) -> Path:
	out_dir = interface.ensure_output_dir(args.out_dir)
	if args.output_csv is None:
		default_name = f"{Path(args.input_wav).stem}_frames.csv"
		output_csv = interface.resolve_output_path(out_dir, Path(default_name))
	else:
		output_csv = interface.resolve_output_path(out_dir, args.output_csv)

	print(f"[extract] loading waveform from {args.input_wav}")
	in_sam, fs = load_audio(args.input_wav)

	modem, wf, demod = interface.build_modem(args, out_dir)

	payload_cls = payload.Payload.get_class(args.payload_type)
	l_frames, l_frame_start_idx = modem.recover_bytes(in_sam)
	print(f"[extract] recovered {len(l_frames)} frames")

	l_payloads, l_payload_start = payload_cls.decode_frames(
		l_frames,
		l_frame_start_idx,
		discard_threshold=args.nonascii_discard_threshold,
	)
	payload_cls.write_csv(l_payloads, l_sam_idx=l_payload_start, out_csv=str(output_csv))

	print(f"[extract] wrote {len(l_payloads)} payload entries to {output_csv}")
	return output_csv

def main(argv: list[str] | None = None):
	parser = interface.build_extract_parser()
	args = parser.parse_args(argv)
	extract_payloads(args)

if __name__ == "__main__":
	main()
