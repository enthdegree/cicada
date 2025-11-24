#!/usr/bin/env python3
"""Verification CLI for SignaturePayloads or PlaintextPayloads."""
from __future__ import annotations

import argparse
from pathlib import Path

from cicada import interface, payload, speech, verification
import extract as extract_cli

def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Verify frames against a transcription.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)
	interface.add_output_dir_arg(parser)
	interface.add_debug_flag(parser)
	interface.add_payload_type_arg(parser)
	interface.add_waveform_args(parser)
	interface.add_demod_args(parser)
	interface.add_ldpc_flags(parser)
	parser.add_argument("--input-wav", type=Path, default=interface.DEFAULT_OUT_DIR / "recording.wav", help="Recording to transcribe.")
	parser.add_argument(
		"--frames-csv",
		type=Path,
		default=None,
		help="CSV produced by extract.py (default: out/frames.csv).",
	)
	parser.add_argument("--output-md", type=Path, default=Path("transcript.md"), help="Where to write annotated markdown.")
	parser.add_argument("--model-size", default="medium.en", help="Whisper model size to use for transcription (signature payloads only).")
	parser.add_argument("--window-sec", type=float, default=10.0, help="Transcription window length in seconds.")
	parser.add_argument("--overlap-sec", type=float, default=8.0, help="Transcription window overlap in seconds.")
	parser.add_argument("--bls-pubkey", type=Path, default=Path("bls_pubkey.bin"), help="BLS public key for SignaturePayload verification.")
	parser.add_argument("--nonascii-discard-threshold", type=int, default=4, help="Max non-ASCII characters allowed in payload content before discarding.")
	return parser

def run_payload_verification(payload_cls, args: argparse.Namespace, frames_csv: Path, output_md: Path):
	from faster_whisper import WhisperModel

	print("[verify] loading Whisper model...")
	model = WhisperModel(args.model_size, compute_type="float32")

	print(f"[verify] loading payloads from {frames_csv}")
	l_payloads, l_payload_start_sam = payload_cls.load_csv(frames_csv)
	l_payloads, l_payload_start_sam = payload_cls.filter_payloads(
		l_payloads,
		l_payload_start_sam,
		ascii_threshold=args.nonascii_discard_threshold,
	)
	print(f"[verify] loaded {len(l_payloads)} payloads, transcribing {args.input_wav}")
	bls_pubkey_bytes = interface.load_bls_pubkey(args.bls_pubkey) if payload_cls.requires_bls_keys else None

	l_chunks, wav_fs_Hz = verification.wav_to_transcript_chunks(
		args.input_wav,
		model,
		window_sec=args.window_sec,
		overlap_sec=args.overlap_sec,
	)

	annotated_md = ""
	n_chunks = len(l_chunks)
	for ichunk, chunk in enumerate(l_chunks, start=1):
		segments = list(chunk.seg_iter)
		chunk_text = "".join(seg.text for seg in segments)
		l_tokens = speech.regularize_transcript(chunk_text)
		l_match_idx = []
		for pl in l_payloads:
			kwargs = {}
			if bls_pubkey_bytes is not None:
				kwargs["bls_pubkey_bytes"] = bls_pubkey_bytes
			l_match_idx.append(pl.match_chunk(chunk_text, **kwargs))
		chunk_md = verification.annotate_chunk(chunk_text, l_tokens, l_payloads, l_match_idx, l_payload_start_sam, wav_fs_Hz)
		start_sec = chunk.idx / wav_fs_Hz
		end_sec = start_sec + chunk.info.duration
		chunk_md = f"# Chunk {ichunk} of {n_chunks}; ({start_sec:.2f}-{end_sec:.2f} s)\n\n" + chunk_md + "\n"
		if args.debug:
			print(chunk_md)
		annotated_md += chunk_md

	annotated_md += verification.write_appendix_md(l_payloads, l_payload_start_sam, wav_fs_Hz)
	output_md.write_text(annotated_md, encoding="utf-8")
	print(f"[verify] wrote {output_md}")

def main(argv: list[str] | None = None):
	parser = build_parser()
	args = parser.parse_args(argv)
	out_dir = interface.ensure_output_dir(args.out_dir)
	output_md = interface.resolve_output_path(out_dir, args.output_md)
	if args.frames_csv is None:
		extract_args = argparse.Namespace(
			out_dir=args.out_dir,
			debug=args.debug,
			payload_type=args.payload_type,
			input_wav=args.input_wav,
			output_csv=Path("frames.csv"),
			nonascii_discard_threshold=args.nonascii_discard_threshold,
			wf_bits_per_symbol=args.wf_bits_per_symbol,
			wf_fs=args.wf_fs,
			wf_fc=args.wf_fc,
			wf_symbol_rate=args.wf_symbol_rate,
			wf_bw=args.wf_bw,
			wf_hop_factor=args.wf_hop_factor,
			wf_mod_pattern=args.wf_mod_pattern,
			demod_symbols_per_frame=args.demod_symbols_per_frame,
			demod_frame_search_win=args.demod_frame_search_win,
			demod_frame_search_step=args.demod_frame_search_step,
			demod_pulse_frac=args.demod_pulse_frac,
			demod_median_window=args.demod_median_window,
			demod_plot=args.demod_plot,
			use_ldpc=args.use_ldpc,
		)
		print("[verify] no frames CSV provided; extracting frames first...")
		frames_csv = extract_cli.extract_payloads(extract_args)
	else:
		frames_csv = args.frames_csv

	payload_cls = payload.get_payload_class(args.payload_type)
	if payload_cls.requires_bls_keys and not args.bls_pubkey.exists():
		parser.error("BLS pubkey required for this payload type.")
	run_payload_verification(payload_cls, args, frames_csv, output_md)

if __name__ == "__main__":
	main()
