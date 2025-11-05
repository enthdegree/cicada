# Speech processing routines
import time, queue, numpy as np, sounddevice as sd
import re 
import number_parser 
from dataclasses import dataclass
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment, TranscriptionInfo
from collections.abc import Iterator

# Model definition
model_size = "medium.en"
model_fs_Hz = 16e3
window_sec = 10.0
overlap_sec = 5.0
mic_blocksize_sam = 1024
model = WhisperModel(model_size, compute_type="float32")

# Transcript definition
@dataclass
class TranscriptChunk: 
	seg_iter: Iterator[Segment] # Iterable of whisper model segments
	info: TranscriptionInfo # Whisper model transcript info
	idx: int = 0 # Sample where this chunk of the transcript starts

@dataclass 
class TranscriptToken:
	text: str # Some text content of the transcript
	idx: int # Character index of where this text starts in the transcript

def regularize_transcript(s): # Convert a string of english into a list of slightly regularized TranscriptTokens
	for dash in ("-", "–", "—"): s = s.replace(dash, " ") # replace dashes with space
	l_tokens = [(m.group(), m.start()) for m in re.finditer(r'\S+', s)] # Split on whitespace to (token, start_index) pairs
	l_tokens_clean = list()
	for itok in range(len(l_tokens)): # Clean each token in the list
		tok = l_tokens[itok][0].lower() # Lowercase
		tok = number_parser.parser.parse(tok) # Word to numeric
		tok = re.sub(r"[^a-z0-9]", "", tok) # Strip non-alphanumeric
		if len(tok) > 0: l_tokens_clean.append(TranscriptToken(text=tok, idx=l_tokens[itok][1]))
	return l_tokens_clean

def mic_producer(q_audio):
	def _callback(indata, frames, time_info, status):
		if status: print("[mic]", status)
		mono = indata.mean(axis=1).copy()
		q_audio.put(mono)

	with sd.InputStream(samplerate=model_fs_Hz,
		channels=1,
		blocksize=mic_blocksize_sam,
		dtype="float32",
		callback=_callback):
		while True: time.sleep(0.1)

# Transcript producer
def transcribe_audio_loop(model, q_audio, q_tokens, debug=True):
	window_samples = int(window_sec * model_fs_Hz)
	overlap_samples = int(overlap_sec * model_fs_Hz)
	hop_samples = window_samples - overlap_samples

	audio_buffer = np.zeros(0, dtype=np.float32)
	next_decode_at = 0.0
	last_debug = 0.0
	while True:
		try:
			chunk = q_audio.get(timeout=0.1)
		except queue.Empty:
			now = time.time()
			if debug and now - last_debug > 2.0:
				print("[loop] no audio yet…")
				last_debug = now
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
		if debug and now - last_debug > 2.0:
			secs = audio_buffer.size / model_fs_Hz
			print(f"[loop] buffer_len={secs:.2f}s")
			last_debug = now

		# need full window
		if audio_buffer.size < window_samples:
			continue

		# throttle
		if now < next_decode_at:
			continue
		next_decode_at = now + (hop_samples / model_fs_Hz)

		# decode latest window
		window_audio = audio_buffer[-window_samples:]
		if debug:
			print("[decode] calling model…")

		try:
			seg_iter, info = model.transcribe(
				window_audio,
				language="en",
				beam_size=1,
				vad_filter=False,
			)
			segments = list(seg_iter)
		except Exception as e:
			print(f"[decode error] {e!r}")
			continue

		# Reformat and publish transcript
		str_transcript_raw = " ".join(s.text.strip() for s in segments if s.text)
		l_tokens = regularize_transcript(str_transcript_raw)
		if len(l_tokens) > 0: q_tokens.put(l_tokens) 
		if debug:
			print("[debug] got regularized string")

