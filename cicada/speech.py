"""Speech transcription & transcript regularization utilities."""
import time, queue, numpy as np, soundfile as sf, sounddevice as sd
from dataclasses import dataclass
from math import gcd
from collections.abc import Iterator
from pathlib import Path
from datetime import datetime, timezone
from scipy.signal import resample_poly
from faster_whisper.transcribe import Segment, TranscriptionInfo

whisper_model_fs_Hz = 16e3 # All Whisper models are trained on 16 kHz samples

@dataclass
class WhisperTranscriptionChunk: 
	seg_iter: Iterator[Segment] # Iterable of whisper model segments
	info: TranscriptionInfo # Whisper model transcript info
	idx: int = -1 #  (if applicable) Sample index of the .wav file where this chunk started

def load_wav(path):
	samples_for_model, wav_fs_Hz = sf.read(path)
	if samples_for_model.ndim > 1: # to mono
		samples_for_model = samples_for_model.mean(axis=1)
	if not (wav_fs_Hz == whisper_model_fs_Hz): # resample
		g = gcd(int(wav_fs_Hz), int(whisper_model_fs_Hz))
		up = whisper_model_fs_Hz / g
		down = wav_fs_Hz / g
		samples_for_model = resample_poly(samples_for_model, up, down)
	return samples_for_model, wav_fs_Hz

def mic_worker(q_audio, mic_blocksize_sam=1024): # Microphone sample producer
	def _callback(indata, frames, time_info, status):
		if status: print("[mic worker]", status)
		mono = indata.mean(axis=1).copy()
		q_audio.put(mono)

	with sd.InputStream(samplerate=whisper_model_fs_Hz,
		channels=1,
		blocksize=mic_blocksize_sam,
		dtype="float32",
		callback=_callback):
		while True: time.sleep(0.1)

def audio_transcript_worker(model, q_audio, q_tokens, window_sec=10.0, overlap_sec=5.0, debug=True, transcript_writer=None): # Audio transcription producer
	window_samples = int(window_sec * whisper_model_fs_Hz)
	overlap_samples = int(overlap_sec * whisper_model_fs_Hz)
	hop_samples = window_samples - overlap_samples
	audio_buffer = np.zeros(0, dtype=np.float32)
	next_decode_at = time.monotonic()
	while True:
		try:
			sam = q_audio.get(timeout=0.1)
			sam = np.asarray(sam, dtype=np.float32).ravel()
			audio_buffer = np.concatenate([audio_buffer, sam])
		except queue.Empty:
			if audio_buffer.size == 0 and debug:
				print("[transcript worker] waiting for audio...")
		if audio_buffer.size < window_samples:
			continue

		if audio_buffer.size > window_samples * 4:
			audio_buffer = audio_buffer[-window_samples * 4 :]

		now = time.monotonic()
		if now < next_decode_at:
			continue
		next_decode_at = now + (hop_samples / whisper_model_fs_Hz)

		window_audio = audio_buffer[-window_samples:]
		if debug: print("[transcript worker] decoding latest window...")
		seg_iter, info = model.transcribe(
			window_audio,
			language="en",
			beam_size=1,
			vad_filter=False,
		)
		segments = list(seg_iter)

		str_transcript_raw = " ".join(s.text.strip() for s in segments if s.text)
		if str_transcript_raw:
			if transcript_writer is not None:
				transcript_writer.write_chunk(str_transcript_raw, timestamp=time.time())
			q_tokens.put(str_transcript_raw)
			if debug: print("[transcript worker] published transcript chunk")

class TranscriptLogger:
	"""Append-only markdown transcript logger."""
	def __init__(self, path: Path):
		self.path = path
		self.path.parent.mkdir(parents=True, exist_ok=True)
		self._fh = open(self.path, "a", encoding="utf-8")
		self._fh.write("# Signer Transcript\n\n")

	def write_chunk(self, chunk_text: str, timestamp: float | None = None):
		ts = timestamp if timestamp is not None else time.time()
		ts_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
		self._fh.write(f"## {ts_str}\n")
		self._fh.write(chunk_text.rstrip() + "\n\n")
		self._fh.flush()

	def close(self):
		self._fh.close()
