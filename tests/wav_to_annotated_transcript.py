"""A counterpart to tx_raw_transcription.py, this script does the following:
	1. Transcribe a wav to English
	2. Look for data frames in the wav
	3. Match the data frames (assumed to contain transcriptions) to the Step 1 transcription 
	4. Annotate the Step 1 transcription with matches
"""
import sys, csv, re, base64
import soundfile as sf
import numpy as np
from math import gcd
from imprint import speech
from imprint.speech import TranscriptChunk
from scipy.signal import resample_poly
from dataclasses import dataclass
from faster_whisper import WhisperModel

# Model used for transcribing input .wav to english
window_sec = 10.0
overlap_sec = 5.0
transcription_model_name = "medium.en" 
transcription_model_fs_Hz = 16e3
transcription_model = WhisperModel(transcription_model_name, compute_type="float32")

def load_csv(path): # Load a csv list of transcripts
	l_base64 = list()
	l_payload_start_sam = list()
	with open(in_csv, newline='') as f:
		reader = csv.DictReader(f)
		for row in reader:
			l_base64.append(row['frame_base64'])
			l_payload_start_sam.append(int(row['frame_start_sam']))
	l_payloads = list()
	for p in l_base64:
		p_txt = base64.b64decode(p).decode('ascii', errors='ignore')
		p_txt = re.match(r"[a-z0-9 ]*", p_txt).group(0)
		l_payloads.append(p_txt.split())
	return l_payloads, l_payload_start_sam
	
def load_wav(path):
	samples, wav_fs_Hz = sf.read(path)
	if samples.ndim > 1: # to mono
		samples = samples.mean(axis=1)
	if not (wav_fs_Hz == transcription_model_fs_Hz): # resample
		g = gcd(int(wav_fs_Hz), int(transcription_model_fs_Hz))
		up = transcription_model_fs_Hz / g
		down = wav_fs_Hz / g
		samples = resample_poly(samples, up, down)
	return samples, wav_fs_Hz

def fmt_time(sec: float) -> str: # mm:ss.xx
	m = int(sec // 60)
	s = sec - 60 * m
	return f"{m:02d}:{s:05.2f}"

def wav_to_chunks(in_wav): # Transcribe a .wav (filename) to chunks of text
	samples, wav_fs_Hz = load_wav(in_wav)
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
		seg_iter, info = transcription_model.transcribe(
			window_samples,
			language="en",
			beam_size=1,
			vad_filter=False,
		)
		l_chunks.append(TranscriptChunk(seg_iter=seg_iter, info=info, idx=win_start_idx))
		win_start_idx += n_shift_sam
	return l_chunks, wav_fs_Hz

def find_sublist(l1, l2): # Find the first index of l2's occurrence in l1
	len1, len2 = len(l1), len(l2)
	if len2 == 0: return -1
	for idx in range(len1 - len2 + 1):
		if l1[idx:(idx + len2)] == l2: return idx
	return -1

def annotate_chunk(chunk_text, l_tokens, l_payloads, l_match_idx, l_payload_start_sam, wav_fs_Hz=44100):
	l_payload_idx = [] # Index of each matching payload in l_payloads
	l_chunk_text_idx = [] # Index of each matching payload in the transcript
	n_p = len(l_payloads)
	for idx in range(n_p): 
		if l_match_idx[idx] >= 0: # -1 if this payload doesn't appear in the chunk, idx if it appears starting at the chunk's i-th token
			l_payload_idx.append(idx)
			l_chunk_text_idx.append(l_tokens[l_match_idx[idx]].idx)
	n_fn = len(l_chunk_text_idx)

	# Sort footnotes so their locations ascend
	order = sorted(range(n_fn), key=lambda idx: l_chunk_text_idx[idx]) 
	l_chunk_text_idx = [l_chunk_text_idx[i] for i in order]
	l_payload_idx = [l_payload_idx[i] for i in order]

	# Write body with footnote markings
	l_body_md = []
	last = 0
	for idxfn, pos in enumerate(l_chunk_text_idx, start=1):
		l_body_md.append(chunk_text[last:pos])
		l_body_md.append(f"[{idxfn}]")
		last = pos
	l_body_md.append(chunk_text[last:])
	body_md = "".join(l_body_md)

	# Write footnotes 
	l_fn = []
	for idxfn in range(n_fn):
		idxpl = l_payload_idx[idxfn]
		n_matched_words = len(l_payloads[idxpl])
		idxsam = l_payloads[idxpl]
		pl_start_sam = l_payload_start_sam[idxpl]
		pl_start_sec = pl_start_sam/wav_fs_Hz
		l_fn.append(f"Payload {idxpl} matches the following {n_matched_words} words, which stated at sample {pl_start_sam} ({pl_start_sec:.2f} sec)")
	notes_md = "\n".join(f"[{idxfn+1}]: {l_fn[idxfn]}" for idxfn in range(n_fn))
	return f"{body_md}\n\n{notes_md}" if notes_md else body_md

if __name__ == "__main__":
	in_wav = sys.argv[1]
	in_csv = sys.argv[2]
	out_md = sys.argv[3]
	
	print(f"Loading frames from {in_csv}...")
	l_payloads, l_payload_start_sam = load_csv(in_csv)

	print(f"Getting transcription chunks from {in_wav}...")
	l_chunks, wav_fs_Hz = wav_to_chunks(in_wav)
	n_chunks = len(l_chunks)
	start_sec = 0.0
	annotated_md = ""
	for ichunk in range(n_chunks):
		chunk = l_chunks[ichunk]

		end_sec = start_sec + chunk.info.duration

		# Collect this chunk's text and convert it to a list of tokens
		chunk_text = ""
		for seg in list(chunk.seg_iter): chunk_text += seg.text
		l_tokens = speech.regularize_transcript(chunk_text)
		
		# Compare our payloads to these tokens
		l_tswords = [tok.text for tok in l_tokens]
		l_match_idx = [] # i-th entry is the index of the i-th payload's first appearance in the chunk
		for p in l_payloads: l_match_idx.append(find_sublist(l_tswords,p))

		# Create markdown for this chunk
		chunk_md = annotate_chunk(chunk_text, l_tokens, l_payloads, l_match_idx, l_payload_start_sam, wav_fs_Hz)
		chunk_md = f"# Chunk {ichunk+1} of {n_chunks}; ({start_sec:.2f}-{end_sec:.2f} s)\n\n" + chunk_md + "\n"
		print(chunk_md)
		annotated_md += chunk_md 
		start_sec += chunk.info.duration

	print(f"Writing {out_md}")
	with open(out_md, "w", encoding="utf-8") as f:
	    f.write(annotated_md)
