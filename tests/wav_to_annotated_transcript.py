"""A counterpart to tx_raw_transcription.py, this script does the following:
	1. Transcribe a wav to English
	2. Look for data frames in the wav
	3. Match the data frames to the transcription and annotate it
"""
import sys
from math import gcd
import numpy as np
from imprint import speech
from scipy.signal import resample_poly
import soundfile as sf
from dataclasses import dataclass
from faster_whisper import WhisperModel
from collections.abc import Iterator
from faster_whisper.transcribe import Segment, TranscriptionInfo

# Model used for transcribing input .wav to english
window_sec = 10.0
overlap_sec = 5.0
transcription_model_name = "medium.en" # or "small.en"
transcription_model_fs_Hz = 16e3
transcription_model = WhisperModel(transcription_model_name, compute_type="float32")

@dataclass
class TranscriptChunk: 
	seg_iter: Iterator[Segment] 
	info: TranscriptionInfo 
	win_start_idx: int

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

def wav_to_chunks(in_wav):
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
		l_chunks.append(TranscriptChunk(seg_iter=seg_iter, info=info, win_start_idx=win_start_idx))
		win_start_idx += n_shift_sam
	return l_chunks

if __name__ == "__main__":
	if len(sys.argv) != 3:
		print("usage: python transcribe_windows.py input.wav frames.csv output.md")
		sys.exit(1)
	in_wav = sys.argv[1]
	in_csv = sys.argv[2]
	out_md = sys.argv[3]
	
	print(f"Loading frames from {in_csv}...")
	get_frames_from_csv()

	print(f"Getting transcription chunks from {in_wav}...")
	l_chunks = wav_to_chunks(in_wav)
	n_chunks = len(l_chunks)
	for ichunk in range(n_chunks):
		chunk = l_chunks[ichunk]

		print(f"Transcribing chunk {ichunk+1} of {n_chunks}...")
		chunk_transcript = ""
		for seg in list(chunk.seg_iter): chunk_transcript += seg.text
		print(chunk_transcript)

		print(f"Regularizing chunk...")
		l_words = speech.regularize_transcript(chunk_transcript)
		
		print("")
