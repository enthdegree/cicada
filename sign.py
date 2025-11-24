#!/usr/bin/env python3
"""Live signer/transmitter CLI."""
from __future__ import annotations

import argparse
import queue
import threading
from pathlib import Path

import sounddevice as sd
from faster_whisper import WhisperModel

from cicada import payload, speech
from cicada import interface

def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Continuously transcribe mic audio and transmit payload frames.",
		formatter_class=argparse.ArgumentDefaultsHelpFormatter,
	)
	interface.add_output_dir_arg(parser)
	interface.add_debug_flag(parser)
	interface.add_payload_type_arg(parser)
	interface.add_waveform_args(parser)
	interface.add_demod_args(parser)
	interface.add_ldpc_flags(parser)
	parser.add_argument("--model-size", default="medium.en", help="Whisper model size.")
	parser.add_argument("--window-sec", type=float, default=10.0, help="Transcription window length (s).")
	parser.add_argument("--overlap-sec", type=float, default=5.0, help="Transcription window overlap (s).")
	parser.add_argument("--mic-blocksize", type=int, default=1024, help="Audio blocksize for microphone capture.")
	parser.add_argument("--signer-transcript", type=Path, default=None, help="Optional path to log raw transcript chunks.")
	parser.add_argument("--header-message", default="q3q.net", help="Header message for SignaturePayloads.")
	parser.add_argument("--bls-privkey", type=Path, default=Path("bls_privkey.bin"), help="Path to BLS private key.")
	parser.add_argument("--bls-pubkey", type=Path, default=Path("bls_pubkey.bin"), help="Path to BLS public key.")
	return parser

def run(args: argparse.Namespace):
	out_dir = interface.ensure_output_dir(args.out_dir)
	modem, wf, demod = interface.build_modem(args, out_dir)

	payload_cls = payload.get_payload_class(args.payload_type)
	model = WhisperModel(args.model_size, compute_type="float32")

	bls_privkey = None
	bls_pubkey_bytes = None
	if payload_cls.requires_bls_keys:
		bls_privkey, bls_pubkey_bytes = interface.load_bls_keypair(args.bls_privkey, args.bls_pubkey)

	q_mic = queue.Queue()
	q_transcripts = queue.Queue()
	t_mic = threading.Thread(
		target=speech.mic_worker,
		args=(q_mic,),
		kwargs={"mic_blocksize_sam": args.mic_blocksize},
		daemon=True,
	)
	transcript_writer = None
	if args.signer_transcript:
		transcript_path = interface.resolve_output_path(out_dir, args.signer_transcript)
		transcript_writer = speech.TranscriptLogger(transcript_path)
	t_transcriber = threading.Thread(
		target=speech.audio_transcript_worker,
		args=(model, q_mic, q_transcripts),
		kwargs={
			"window_sec": args.window_sec,
			"overlap_sec": args.overlap_sec,
			"debug": args.debug,
			"transcript_writer": transcript_writer,
		},
		daemon=True,
	)
	t_mic.start()
	t_transcriber.start()

	print(f"[sign] transmitting {args.payload_type} payloads (LDPC={'on' if args.use_ldpc else 'off'})")
	while True:
		chunk_text = None
		try:
			while True:
				chunk_text = q_transcripts.get_nowait()
		except queue.Empty:
			pass
		if chunk_text is None:
			chunk_text = q_transcripts.get()
		print(f"[sign] {chunk_text}")

		payload_kwargs = {}
		if payload_cls.requires_bls_keys:
			payload_kwargs.update(
				header_message=args.header_message,
				bls_privkey=bls_privkey,
				bls_pubkey_bytes=bls_pubkey_bytes,
			)
		pl = payload_cls.from_transcript(chunk_text, **payload_kwargs)
		pl_bytes = pl.to_bytes()

		frame_samples = modem.modulate_bytes(pl_bytes)
		sd.play(frame_samples, wf.fs_Hz)
		sd.wait()

def main(argv: list[str] | None = None):
	parser = build_parser()
	args = parser.parse_args(argv)
	payload_cls = payload.get_payload_class(args.payload_type)
	if payload_cls.requires_bls_keys and (not args.bls_privkey.exists() or not args.bls_pubkey.exists()):
		parser.error("BLS key paths must exist when payload-type=signature.")
	run(args)

if __name__ == "__main__":
	main()
