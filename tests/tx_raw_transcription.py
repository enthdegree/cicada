#!/usr/bin/env python3
"""Minimal mic→transcript→frame TX loop using current cicada APIs."""
import sys 
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

import queue
import threading
import sounddevice as sd
from faster_whisper import WhisperModel

from cicada import payload, speech
from cicada.modem import Modem
from cicada.fsk.waveform import FSKWaveform, FSKParameters, default_mod_table
from cicada.fsk.demodulator import FSKDemodulator, FSKDemodulatorParameters

# Build a minimal modem (TX only; demod not used here)
wf = FSKWaveform()
demod = FSKDemodulator(FSKDemodulatorParameters(), wf=wf)
modem = Modem(wf, demodulator=demod, use_ldpc=True, use_bit_mask=True)

payload_cls = payload.Payload.get_class("plaintext")

# Design and construct speech transcription threads
model_size = "medium.en"
transcript_path = Path("./tx_raw_transcription_transcript.md")
window_sec = 10.0
overlap_sec = 3.0
debug = True
transcript_writer = speech.TranscriptLogger(transcript_path)
model = WhisperModel(model_size, compute_type="float32")

q_mic = queue.Queue()
q_transcripts = queue.Queue()
t_mic = threading.Thread(target=speech.mic_worker, args=(q_mic,), daemon=True)
t_transcriber = threading.Thread(
	target=speech.audio_transcript_worker,
	args=(model, q_mic, q_transcripts),
	kwargs={
		"window_sec": window_sec,
		"overlap_sec": overlap_sec,
		"debug": debug,
		"transcript_writer": transcript_writer,
	},
	daemon=True,
)
t_mic.start()
t_transcriber.start()

print("[tx] capturing mic, transcribing, and transmitting plaintext payloads...")
while True:
	chunk_text = None
	try:
		while True:
			chunk_text = q_transcripts.get_nowait()
	except queue.Empty:
		pass
	if chunk_text is None:
		chunk_text = q_transcripts.get()
	print(f"[tx] {chunk_text}")

	pl = payload_cls.from_transcript(chunk_text)
	samples = modem.modulate_bytes(pl.to_bytes())
	sd.play(samples, wf.fs_Hz)
	sd.wait()
