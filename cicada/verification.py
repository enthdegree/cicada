"""Utilities for comparing transcription chunks to SignaturePayloads."""
import time, numpy as np
from cicada import speech
from cicada.speech import WhisperTranscriptionChunk

def fmt_time(sec: float) -> str: # mm:ss.xx
	m = int(sec // 60)
	s = sec - 60 * m
	return f"{m:02d}:{s:05.2f}"

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

def find_sublist(l1, l2): # Find the first index of l2's occurrence in l1
	len1, len2 = len(l1), len(l2)
	if len2 == 0: return -1
	for idx in range(len1 - len2 + 1):
		if l1[idx:(idx + len2)] == l2: return idx
	return -1

def make_footnote(pl, slug, start_sam, wav_fs_Hz=44100):
	start_desc = f"sample {start_sam}" if start_sam is not None else "unknown sample"
	start_sec = (start_sam / wav_fs_Hz) if (start_sam is not None and wav_fs_Hz) else None
	ts_str = time.ctime(pl.header.timestamp)
	return (
		f"[{slug}]: Payload at timestamp {ts_str} matches "
		f"{pl.header.word_count} words near {start_desc}"
		f"{f' ({start_sec:.2f} sec)' if start_sec is not None else ''}. "
		f"Header message: {pl.header.message}"
	)

def annotate_chunk(chunk_text, l_tokens, l_payloads, l_match_idx, l_payload_start_sam, wav_fs_Hz=44100):
	l_payload_idx = [] # Index of each matching payload in l_payloads
	l_chunk_text_idx = [] # Index of each matching payload in the transcript
	n_p = len(l_payloads)
	for idx in range(n_p): 
		if l_match_idx[idx] >= 0: # -1 if this payload doesn't appear in the chunk, idx if it appears starting at the chunk's i-th token
			l_payload_idx.append(idx)
			l_chunk_text_idx.append(l_tokens[l_match_idx[idx]].idx)
	n_fn = len(l_chunk_text_idx)

	# Sort footnotes so their locations ascend (keep pairs together to avoid aliasing issues)
	pairs = sorted(zip(l_chunk_text_idx, l_payload_idx), key=lambda t: t[0])
	l_chunk_text_idx, l_payload_idx = map(list, zip(*pairs)) if pairs else ([], [])

	# Write body with footnote markings
	l_body_md = []
	last = 0
	for idxfn, pos in enumerate(l_chunk_text_idx):
		slug = l_payload_idx[idxfn]+1 # Footnote slug is 1-indexed
		l_body_md.append(chunk_text[last:pos])
		l_body_md.append(f"[{slug}]")
		last = pos
	l_body_md.append(chunk_text[last:])
	body_md = "".join(l_body_md)

	# Write footnotes 
	l_footnotes = []
	for idxfn in range(n_fn):
		idxpl = l_payload_idx[idxfn]
		fn = make_footnote(l_payloads[idxpl], idxpl+1, l_payload_start_sam[idxpl], wav_fs_Hz)
		l_footnotes.append(fn)
	notes_md = "\n".join(l_footnotes)
	return f"{body_md}\n\n{notes_md}\n\n" if notes_md else body_md

def write_appendix_md(l_payloads, l_payload_start_sam=None, wav_fs_Hz: float = 44100.0) -> str:
	appendix_md = "\n\n# Appendix: All Detected Payloads\n"
	lines = []
	for idxpl, pl in enumerate(l_payloads):
		lines.append(f"[{idxpl+1}]: {pl.describe(l_payload_start_sam[idxpl], wav_fs_Hz)}")
	return appendix_md + "\n".join(lines) + "\n"
