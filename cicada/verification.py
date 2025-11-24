"""Utilities for comparing transcription wav or text to Payloads."""
import argparse, shlex, sys, numpy as np, re
from pathlib import Path
from cicada import speech
from cicada.speech import WhisperTranscriptionChunk
from cicada import interface

def wav_to_transcript_chunks(in_wav, model, window_sec = 12.0, overlap_sec = 8.0): 
	''' Transcribe a .wav (filename) to chunks of text '''
	samples, wav_fs_Hz = speech.load_wav(in_wav)
	n_window_sam = int(window_sec * wav_fs_Hz)
	n_overlap_sam = int(overlap_sec * wav_fs_Hz)
	n_shift_sam = n_window_sam - n_overlap_sam
	n_total_sam = len(samples)
	win_start_idx = 0
	l_chunks = list()
	while win_start_idx < n_total_sam:
		win_end_idx = win_start_idx + n_window_sam
		window_samples = samples[win_start_idx:win_end_idx]
		if len(window_samples) < n_window_sam:
			pad = np.zeros(n_window_sam - len(window_samples), dtype=window_samples.dtype)
			window_samples = np.concatenate([window_samples, pad], axis=0)
		seg_iter, info = model.transcribe(
			window_samples,
			language="en",
			beam_size=1,
			vad_filter=False,
		)
		l_chunks.append(WhisperTranscriptionChunk(seg_iter=seg_iter, info=info, idx=win_start_idx))
		win_start_idx += n_shift_sam
	return l_chunks, wav_fs_Hz

def write_appendix_md(l_payloads, l_payload_start_sam=None, wav_fs_Hz: float = 44100.0) -> str:
	appendix_md = "# Appendix: All Detected Payloads\n"
	lines = []
	for idxpl, pl in enumerate(l_payloads):
		lines.append(f"[{idxpl+1}]: {pl.describe(l_payload_start_sam[idxpl], wav_fs_Hz)}")
	return appendix_md + "\n".join(lines) 

def load_markdown_transcript(path: Path):
	raw = path.read_text(encoding="utf-8")
	lines = []
	for line in raw.splitlines():
		if line.lstrip().startswith("#"):
			continue
		if re.match(r"^\s*\[.*\]", line):
			continue
	lines.append(line)
	return "\n".join(lines)

def run_verification(payload_cls, args: argparse.Namespace, frames_csv: Path, output_md: Path):
	print(f"[verification] loading payloads from {frames_csv}")
	l_payloads, l_payload_start_sam = payload_cls.load_csv(frames_csv)
	l_payloads, l_payload_start_sam = payload_cls.filter_payloads(
		l_payloads,
		l_payload_start_sam,
		ascii_threshold=args.nonascii_discard_threshold,
	)
	payload_kwargs = vars(args)
	if payload_cls.requires_bls_keys and "bls_pubkey" in payload_kwargs:
		payload_kwargs["bls_pubkey_bytes"] = interface.load_bls_pubkey(args.bls_pubkey)

	try:
		cmd = shlex.join(sys.argv)
	except AttributeError:
		cmd = " ".join(shlex.quote(a) for a in sys.argv)

	annotated_md = "This file was generated with the following command:\n\n```\n" + cmd + "\n```\n\n"
	if args.input_md:
		transcript_text = load_markdown_transcript(args.input_md)
		chunk_md = payload_cls.annotate_chunk(transcript_text, l_payloads, l_payload_start_sam, payload_kwargs, wav_fs_Hz=44100.0)
		chunk_md = "# Transcript (markdown input)\n\n" + chunk_md
		print(chunk_md, end="")
		annotated_md += chunk_md
	else:
		from faster_whisper import WhisperModel

		print("[verification] loading Whisper model...")
		model = WhisperModel(args.model_size, compute_type="float32")
		print(f"[verification] loaded {len(l_payloads)} payloads, transcribing {args.input_wav}")
		l_chunks, wav_fs_Hz = wav_to_transcript_chunks(
			args.input_wav,
			model,
			window_sec=args.window_sec,
			overlap_sec=args.overlap_sec,
		)
		annotated_md = f"# Transcript of {Path(args.input_wav).name}\n\n"
		n_chunks = len(l_chunks)
		for ichunk, chunk in enumerate(l_chunks, start=1):
			segments = list(chunk.seg_iter)
			chunk_text = "".join(seg.text for seg in segments).lstrip()
			chunk_md = payload_cls.annotate_chunk(chunk_text, l_payloads, l_payload_start_sam, payload_kwargs, wav_fs_Hz)
			start_sec = chunk.idx / wav_fs_Hz
			end_sec = start_sec + chunk.info.duration
			chunk_md = f"## Chunk {ichunk} of {n_chunks}; ({start_sec:.2f}-{end_sec:.2f} s)\n" + chunk_md
			print(chunk_md, end="")
			annotated_md += chunk_md

	annotated_md += write_appendix_md(l_payloads, l_payload_start_sam, 44100.0)
	output_md.write_text(annotated_md, encoding="utf-8")
	print(f"[verification] wrote {output_md}")
