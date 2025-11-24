#!/usr/bin/env python3
"""Extract payload frames from a recording."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

from cicada import payload, interface
from cicada.interface import WrappedHelpFormatter

def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Demodulate frames from a WAV file and write them to CSV.",
		formatter_class=lambda prog: WrappedHelpFormatter(prog, width=80),
	)
	interface.add_output_dir_arg(parser)
	interface.add_debug_flag(parser)
	interface.add_payload_type_arg(parser)
	interface.add_waveform_args(parser)
	interface.add_demod_args(parser)
	interface.add_modem_flags(parser)
	parser.add_argument(
		"--input-wav",
		type=Path,
		default=interface.DEFAULT_OUT_DIR / "recording.wav",
		help="Input WAV file to analyze.",
	)
	parser.add_argument(
		"--output-csv",
		type=Path,
		default=None,
		help="Filename (relative to out-dir unless absolute) for extracted payload metadata.",
	)
	parser.add_argument(
		"--nonascii-discard-threshold",
		type=int,
		default=0,
		help="Maximum allowed non-ASCII characters allowed in a text field before discarding a payload.",
	)
	return parser

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

	payload_cls = payload.get_payload_class(args.payload_type)
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
	parser = build_parser()
	args = parser.parse_args(argv)
	extract_payloads(args)

if __name__ == "__main__":
	main()
