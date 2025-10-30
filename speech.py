# Speech processing & transcription helpers
import time, queue, numpy as np, sounddevice as sd
import re
from number_parser import parser
from faster_whisper import WhisperModel
model_size = "medium.en"
model = WhisperModel(model_size, compute_type="float32")
sample_rate_Hz = 16000
chunk_len_sam = 1024

def regularize_transcript(str_english):
	str_reg = re.sub(r"\s+", " ", str_english)
	for dash in ("-", "–", "—"): str_reg = str_reg.replace(dash, "-")
	str_reg = parser.parse(str_reg) 
	str_reg = str_reg.replace("-", " ") # Strip hyphens
	str_reg = str_reg.lower()
	str_reg = re.sub(r"[^a-z0-9 ]", "", str_reg)
	str_reg = re.sub(r"\s+", " ", str_reg).strip() 
	return str_reg

def transcribe_audio_loop(model, sample_rate, q_audio, q_text, debug=True):
	window_sec = 10.0
	overlap_sec = 5.0
	window_samples = int(window_sec * sample_rate)
	overlap_samples = int(overlap_sec * sample_rate)
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
			secs = audio_buffer.size / sample_rate
			print(f"[loop] buffer_len={secs:.2f}s")
			last_debug = now

		# need full window
		if audio_buffer.size < window_samples:
			continue

		# throttle
		if now < next_decode_at:
			continue
		next_decode_at = now + (hop_samples / sample_rate)

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
		str_transcript_reg = regularize_transcript(str_transcript_raw)
		if str_regularized.strip(): q_text.put(str_regularized.encode('ascii')) 
		if debug:
			print("[debug] got regularized string")

def mic_producer(sample_rate, blocksize, q_audio):
	def _callback(indata, frames, time_info, status):
		if status:
			print("[mic]", status)
		# mono
		q_audio.put(indata[:, 0].copy())

	with sd.InputStream(samplerate=sample_rate,
		channels=1,
		blocksize=blocksize,
		dtype="float32",
		callback=_callback):
		while True: time.sleep(0.1)


