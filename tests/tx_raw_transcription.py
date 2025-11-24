#!/usr/bin/env python3
"""Minimal mic→transcript→frame TX loop using current cicada APIs."""
import queue
import threading
import sounddevice as sd
from pathlib import Path
from cicada import payload, speech, interface
from cicada.modem import Modem
from cicada.fsk.waveform import FSKWaveform, FSKParameters, default_mod_table
from cicada.fsk.demodulator import FSKDemodulator, FSKDemodulatorParameters

# Build a minimal modem (TX only; demod not used here)
wf = FSKWaveform(FSKParameters(mod_table_fn=lambda m=default_mod_table: m()))
demod = FSKDemodulator(FSKDemodulatorParameters(), wf=wf)
modem = Modem(wf, demodulator=demod, use_ldpc=True, use_bit_mask=True)

payload_cls = payload.Payload.get_class("plaintext")

q_mic = queue.Queue()
q_text = queue.Queue()

t_mic = threading.Thread(target=speech.mic_worker, args=(q_mic,), daemon=True)
t_transcriber = threading.Thread(
	target=speech.audio_transcript_worker,
	args=(speech.WhisperModel("medium.en", compute_type="float32"), q_mic, q_text),
	kwargs={"window_sec": 5.0, "overlap_sec": 2.5, "debug": True},
	daemon=True,
)
t_mic.start()
t_transcriber.start()

print("[tx] capturing mic, transcribing, and transmitting plaintext payloads...")
while True:
	chunk_text = None
	try:
		while True:
			chunk_text = q_text.get_nowait()
	except queue.Empty:
		pass
	if chunk_text is None:
		chunk_text = q_text.get()
	print(f"[tx] {chunk_text}")

	pl = payload_cls.from_transcript(chunk_text)
	samples = modem.modulate_bytes(pl.to_bytes())
	sd.play(samples, wf.fs_Hz)
	sd.wait()
