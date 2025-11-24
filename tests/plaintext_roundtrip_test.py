#!/usr/bin/env python3
"""Round-trip regression for PlaintextPayload modulation/demodulation."""
from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

import random
from functools import partial
import numpy as np
import soundfile as sf

from cicada import payload
from cicada.modem import Modem
from cicada.fsk.waveform import FSKParameters, FSKWaveform, default_mod_table
from cicada.fsk.demodulator import FSKDemodulatorParameters, FSKDemodulator

# --- configurable options ---------------------------------------------------
USE_LDPC = True
NOISE_SNR_DB = 30.0  # set to None for noiseless generation
NOISE_SEED = 1337
FRAME_GAP_SEC = 0.75
PRE_PAD_SEC = 3.0
POST_PAD_SEC = 3.0
PLAINTEXT_LEN = 64
N_PAYLOADS = 3
PAYLOAD_TEXTS: list[str] = []  # leave empty to auto-generate randomized phrases
OUTPUT_WAV = Path("plaintext_payload_roundtrip.wav")
PLOT_DEMOD = False
# ----------------------------------------------------------------------------

PLAINTEXT_CLASS = payload.get_payload_class("plaintext")

DEFAULT_WORDS = [
	"alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel","india","juliet",
	"kilo","lima","mike","november","oscar","papa","quebec","romeo","sierra","tango",
	"uniform","victor","whiskey","xray","yankee","zulu"
]
_rng = random.Random(2025)

def _random_phrase(word_count: int = 12) -> str:
	return " ".join(_rng.choice(DEFAULT_WORDS) for _ in range(word_count))

def default_payload_texts() -> list[str]:
	if PAYLOAD_TEXTS:
		return PAYLOAD_TEXTS
	return [_random_phrase() for _ in range(N_PAYLOADS)]

def sanitize_payload_texts(texts: list[str]) -> list[str]:
	seen = set()
	result = []
	for text in texts:
		if not text.isascii():
			continue
		if text in seen:
			continue
		seen.add(text)
		result.append(text)
	return result

def add_awgn(signal: np.ndarray, snr_db: float | None, seed: int) -> np.ndarray:
	if snr_db is None:
		return signal
	rng = np.random.default_rng(seed)
	sig_power = np.mean(signal**2) or 1e-12
	noise_power = sig_power / (10 ** (snr_db / 10))
	noise = rng.normal(0.0, np.sqrt(noise_power), size=signal.shape)
	return signal + noise.astype(signal.dtype, copy=False)

def synthesize_frames(modem: Modem, l_payload_bytes: list[bytes], fs_Hz: float) -> np.ndarray:
	gap_samples = int(round(FRAME_GAP_SEC * fs_Hz))
	pre_pad = np.zeros(int(round(PRE_PAD_SEC * fs_Hz)), dtype=np.float32)
	post_pad = np.zeros(int(round(POST_PAD_SEC * fs_Hz)), dtype=np.float32)

	segments = [pre_pad]
	for idx, pl_bytes in enumerate(l_payload_bytes):
		frame = modem.modulate_bytes(pl_bytes)
		segments.append(frame)
		if idx != len(l_payload_bytes) - 1 and gap_samples > 0:
			segments.append(np.zeros(gap_samples, dtype=np.float32))
	segments.append(post_pad)
	return np.concatenate(segments, axis=0)

def verify_round_trip(expected_payloads: list[payload.Payload], modem: Modem, samples: np.ndarray):
	recovered_bytes, start_idxs = modem.recover_bytes(samples)
	if len(recovered_bytes) != len(expected_payloads):
		raise AssertionError(f"Recovered {len(recovered_bytes)} frames but expected {len(expected_payloads)}.")
	for idx, (pl_expected, recovered, start_idx) in enumerate(zip(expected_payloads, recovered_bytes, start_idxs)):
		expected_bytes = pl_expected.to_bytes()
		recovered = recovered[:len(expected_bytes)]
		pl_actual = PLAINTEXT_CLASS.from_bytes(recovered)
		if pl_actual.content != pl_expected.content:
			raise AssertionError(f"Payload {idx} mismatch at sample {start_idx}: {pl_actual.content!r} != {pl_expected.content!r}")

def main():
	texts = default_payload_texts()

	wf_params = FSKParameters(
		symbol_rate_Hz=(44100.0 / 128.0),
		hop_factor=63,
		mod_table_fn=partial(default_mod_table, pattern=16),
	)
	wf = FSKWaveform(wf_params)
	demod_params = FSKDemodulatorParameters(
		symbols_per_frame=1024,
		frame_search_win=1.2,
		frame_search_win_step=0.3,
		pulse_frac=8,
		plot=PLOT_DEMOD,
	)
	demod = FSKDemodulator(cfg=demod_params, wf=wf)
	modem = Modem(wf, demodulator=demod, use_ldpc=USE_LDPC)

	texts = sanitize_payload_texts(texts)
	if not texts:
		raise ValueError("No valid plaintext payloads after filtering.")
	l_payloads = [PLAINTEXT_CLASS.from_transcript(text) for text in texts]
	l_payload_bytes = [pl.to_bytes() for pl in l_payloads]

	raw_signal = synthesize_frames(modem, l_payload_bytes, wf.fs_Hz)
	noisy_signal = add_awgn(raw_signal, NOISE_SNR_DB, NOISE_SEED)
	sf.write(OUTPUT_WAV, noisy_signal, int(wf.fs_Hz))
	print(f"Wrote {OUTPUT_WAV} ({len(noisy_signal)/wf.fs_Hz:.2f} s).")

	recorded, fs = sf.read(OUTPUT_WAV, dtype="float32", always_2d=False)
	if recorded.ndim > 1:
		recorded = recorded.mean(axis=1)
	if fs != int(wf.fs_Hz):
		raise ValueError(f"Sample-rate mismatch: expected {wf.fs_Hz} Hz, got {fs} Hz.")

	verify_round_trip(l_payloads, modem, recorded.astype(np.float32))
	for idx, pl in enumerate(l_payloads, start=1):
		print(f"[ok] Frame {idx}: {pl.content}")

if __name__ == "__main__":
	main()
