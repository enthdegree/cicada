#!/usr/bin/env python3
"""Verification CLI for SignaturePayloads or PlaintextPayloads."""
from __future__ import annotations
import argparse
from pathlib import Path
import extract as extract_cli
from cicada import interface, payload, verification

def main(argv: list[str] | None = None):
	parser = interface.build_verify_parser()
	args = parser.parse_args(argv)
	out_dir = interface.ensure_output_dir(args.out_dir)
	in_path = args.input
	is_markdown = in_path.suffix.lower() == ".md"
	args.input_md = in_path if is_markdown else None
	args.input_wav = None if is_markdown else in_path

	if args.output_md is None:
		default_transcript = Path(f"{in_path.stem}_transcript.md")
		output_md = interface.resolve_output_path(out_dir, default_transcript)
	else:
		output_md = interface.resolve_output_path(out_dir, args.output_md)

	if args.frames_csv is None:
		if args.input_wav is None:
			parser.error("A frames CSV is required when verifying from a markdown transcript.")
		extract_args = argparse.Namespace(
			out_dir=args.out_dir,
			debug=args.debug,
			payload_type=args.payload_type,
			input_wav=args.input_wav,
			output_csv=Path(f"{Path(args.input_wav).stem}_frames.csv"),
			nonascii_discard_threshold=args.nonascii_discard_threshold,
			wf_bits_per_symbol=args.wf_bits_per_symbol,
			wf_fs=args.wf_fs,
			wf_fc=args.wf_fc,
			wf_symbol_rate=args.wf_symbol_rate,
			wf_bw=args.wf_bw,
			wf_hop_factor=args.wf_hop_factor,
			wf_symbols_per_frame=args.wf_symbols_per_frame,
			wf_mod_pattern=args.wf_mod_pattern,
			demod_frame_search_win=args.demod_frame_search_win,
			demod_frame_search_step=args.demod_frame_search_step,
			demod_pulse_frac=args.demod_pulse_frac,
			demod_highpass=args.demod_highpass,
			demod_plot=args.demod_plot,
			use_ldpc=args.use_ldpc,
			discard_duplicate_frames=args.discard_duplicate_frames,
		)
		print("[verify] no frames CSV provided; extracting frames first...")
		frames_csv = extract_cli.extract_payloads(extract_args)
	else:
		frames_csv = args.frames_csv

	payload_cls = payload.Payload.get_class(args.payload_type)
	if payload_cls.requires_bls_keys and not args.bls_pubkey.exists():
		parser.error("BLS pubkey required for this payload type.")
	verification.run_verification(payload_cls, args, frames_csv, output_md)

if __name__ == "__main__":
	main()
