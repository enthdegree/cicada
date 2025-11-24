"""Speech transcription & transcript regularization utilities."""
import time, queue, re, number_parser, numpy as np, soundfile as sf, sounddevice as sd
from dataclasses import dataclass
from math import gcd
from collections.abc import Iterator
from scipy.signal import resample_poly
from faster_whisper.transcribe import Segment, TranscriptionInfo

whisper_model_fs_Hz = 16e3 # All Whisper models are trained on 16 kHz samples

@dataclass
class WhisperTranscriptionChunk: 
	seg_iter: Iterator[Segment] # Iterable of whisper model segments
	info: TranscriptionInfo # Whisper model transcript info
	idx: int = -1 #  (if applicable) Sample index of the .wav file where this chunk started

@dataclass 
class TranscriptToken:
	text: str # Some text content of the transcript
	idx: int # Character index of where this text starts in the transcript

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

def regularize_transcript(s): # Convert a string of english into a list of regularized TranscriptTokens
	for dash in ("-", "–", "—"): s = s.replace(dash, " ") # replace dashes with space
	l_tokens = [(m.group(), m.start()) for m in re.finditer(r'\S+', s)] # Split on whitespace to (token, start_index) pairs
	l_tokens_clean = list()
	for itok in range(len(l_tokens)): # Clean each token in the list
		tok = l_tokens[itok][0].lower() # Lowercase
		tok = number_parser.parser.parse(tok) # Word to numeric
		tok = re.sub(r"[^a-z0-9]", "", tok) # Strip non-alphanumeric
		if len(tok) > 0: l_tokens_clean.append(TranscriptToken(text=tok, idx=l_tokens[itok][1]))
	return l_tokens_clean

def mic_worker(q_audio, mic_blocksize_sam=1024): # Microphone sample producer
	def _callback(indata, frames, time_info, status):
		if status: print("[mic]", status)
		mono = indata.mean(axis=1).copy()
		q_audio.put(mono)

	with sd.InputStream(samplerate=whisper_model_fs_Hz,
		channels=1,
		blocksize=mic_blocksize_sam,
		dtype="float32",
		callback=_callback):
		while True: time.sleep(0.1)

def audio_transcript_worker(model, q_audio, q_tokens, window_sec=10.0, overlap_sec=5.0, debug=True): # Audio transcription producer
	window_samples = int(window_sec * whisper_model_fs_Hz)
	overlap_samples = int(overlap_sec * whisper_model_fs_Hz)
	hop_samples = window_samples - overlap_samples

	audio_buffer = np.zeros(0, dtype=np.float32)
	next_decode_at = 0.0
	while True:
		try: chunk = q_audio.get(timeout=0.1)
		except queue.Empty:
			now = time.time()
			if debug: print("[loop] no audio yet…")
			continue

		chunk = np.asarray(chunk, dtype=np.float32).ravel()
		audio_buffer = np.concatenate([audio_buffer, chunk])

		# drain extras
		while not q_audio.empty():
			extra = np.asarray(q_audio.get(), dtype=np.float32).ravel()
			audio_buffer = np.concatenate([audio_buffer, extra])

		# bound buffer
		if audio_buffer.size > window_samples * 4:
			audio_buffer = audio_buffer[-window_samples * 4 :]

		now = time.time()
		if debug:
			secs = audio_buffer.size / whisper_model_fs_Hz
			print(f"[loop] buffer_len={secs:.2f}s")

		# need full window
		if audio_buffer.size < window_samples: continue

		# throttle
		if now < next_decode_at: continue
		next_decode_at = now + (hop_samples / whisper_model_fs_Hz)

		# decode latest window
		window_audio = audio_buffer[-window_samples:]
		if debug: print("[decode] calling model…")
		seg_iter, info = model.transcribe(
			window_audio,
			language="en",
			beam_size=1,
			vad_filter=False,
		)
		segments = list(seg_iter)

		# Reformat and publish transcript
		str_transcript_raw = " ".join(s.text.strip() for s in segments if s.text)
		l_tokens = regularize_transcript(str_transcript_raw)
		if len(l_tokens) > 0: q_tokens.put(l_tokens) 
		if debug: print("[debug] got regularized string")