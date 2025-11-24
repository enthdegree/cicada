#!/usr/bin/env python3
"""Round-trip test for PlaintextPayload modulation/demodulation."""
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
USE_BIT_MASK = True
SAMPLE_SNR_DB = 10  # set to None for noiseless generation
NOISE_SEED = 0
FRAME_GAP_SEC = 0.12
PRE_PAD_SEC = 0.0
POST_PAD_SEC = 0.1
PLAINTEXT_LEN = 128
N_PAYLOADS = 5
PAYLOAD_TEXTS: list[str] = []  # leave empty to auto-generate randomized phrases
OUTPUT_WAV = Path("plaintext_payload_roundtrip.wav")
PLOT_DEMOD = True
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
	if PAYLOAD_TEXTS: return PAYLOAD_TEXTS
	return [_random_phrase() for _ in range(N_PAYLOADS)]

def add_awgn(signal: np.ndarray, snr_db: float | None, seed: int) -> np.ndarray:
	if snr_db is None:
		return signal
	rng = np.random.default_rng(seed)
	sig_power = np.mean(signal**2) or 1e-12
	noise_power = sig_power / (10 ** (snr_db / 10))
	noise = rng.normal(0.0, np.sqrt(noise_power), size=signal.shape)
	return signal + noise.astype(signal.dtype, copy=False)

def synthesize_frames(modem: Modem, l_payload_bytes: list[bytes], fs_Hz: float):
	gap_samples = int(round(FRAME_GAP_SEC * fs_Hz))
	pre_pad = np.zeros(int(round(PRE_PAD_SEC * fs_Hz)), dtype=np.float32)
	post_pad = np.zeros(int(round(POST_PAD_SEC * fs_Hz)), dtype=np.float32)

	segments = [pre_pad]
	start_samples = []
	cursor = len(pre_pad)
	for idx, pl_bytes in enumerate(l_payload_bytes):
		frame = modem.modulate_bytes(pl_bytes)
		start_samples.append(cursor)
		segments.append(frame)
		cursor += len(frame)
		if idx != len(l_payload_bytes) - 1 and gap_samples > 0:
			segments.append(np.zeros(gap_samples, dtype=np.float32))
			cursor += gap_samples
	segments.append(post_pad)
	return np.concatenate(segments, axis=0), start_samples

def verify_round_trip(expected_payloads: list[payload.Payload], expected_starts: list[int], modem: Modem, samples: np.ndarray):
	recovered_bytes, start_idxs = modem.recover_bytes(samples)
	l_matches_who: list[list[int]] = []
	for rec_bytes in recovered_bytes:
		null_pos = rec_bytes.find(b"\x00")
		rec_effective_len = null_pos if null_pos >= 0 else len(rec_bytes)
		rec_effective = rec_bytes[:rec_effective_len]
		matches = []
		for i, exp in enumerate(expected_payloads):
			exp_bytes = exp.to_bytes()
			compare_len = min(len(exp_bytes), len(rec_effective))
			exp_prefix = exp_bytes[:compare_len]
			rec_prefix = rec_effective[:compare_len]
			if rec_prefix == exp_prefix:
				matches.append(i)
		l_matches_who.append(matches)
	return recovered_bytes, start_idxs, l_matches_who

def main():
	texts = default_payload_texts()

	wf_params = FSKParameters(
		symbol_rate_Hz=(44100.0 / 128.0),
		hop_factor=63,
		mod_table_fn=partial(default_mod_table, pattern=16),
	)
	wf = FSKWaveform(wf_params)
	demod_params = FSKDemodulatorParameters(
		frame_search_win=1.2,
		frame_search_win_step=0.3,
		pulse_frac=8,
		high_pass_len_pulses=8,
		plot=PLOT_DEMOD,
	)
	out_dir = Path("out")
	demod = FSKDemodulator(cfg=demod_params, wf=wf, plot_dir=out_dir)
	modem = Modem(wf, demodulator=demod, use_ldpc=USE_LDPC, use_bit_mask=USE_BIT_MASK)

	l_payloads = [PLAINTEXT_CLASS.from_transcript(text[:modem.bytes_per_frame]) for text in texts]
	l_payload_bytes = [pl.to_bytes() for pl in l_payloads]

	raw_signal, expected_starts = synthesize_frames(modem, l_payload_bytes, wf.fs_Hz)
	noisy_signal = add_awgn(raw_signal, SAMPLE_SNR_DB, NOISE_SEED)
	sf.write(OUTPUT_WAV, noisy_signal, int(wf.fs_Hz))
	print(f"Wrote {OUTPUT_WAV} ({len(noisy_signal)/wf.fs_Hz:.2f} s).")

	recorded, fs = sf.read(OUTPUT_WAV, dtype="float32", always_2d=False)
	if recorded.ndim > 1:
		recorded = recorded.mean(axis=1)
	if fs != int(wf.fs_Hz):
		raise ValueError(f"Sample-rate mismatch: expected {wf.fs_Hz} Hz, got {fs} Hz.")

	recovered_bytes, start_idxs, l_matches_who = verify_round_trip(l_payloads, expected_starts, modem, recorded.astype(np.float32))
	for i, start in enumerate(expected_starts):
		match_indices = [j for j, matches in enumerate(l_matches_who) if i in matches]
		if match_indices:
			match_str = ", ".join(str(j+1) for j in match_indices)
			print(f"Expected payload {i+1} at sample {start} matched recovered payload(s): {match_str}")
		else:
			print(f"Expected payload {i+1} at sample {start} matched recovered payload(s): none")

	for j, matches in enumerate(l_matches_who):
		if not matches:
			print(f"Payload found at index {start_idxs[j]} does not match any expected payloads.")

	n_matched = sum(1 for i in range(len(l_payloads)) if any(i in matches for matches in l_matches_who))
	print(f"Summary: {n_matched}/{len(l_payloads)} payloads matched")

if __name__ == "__main__": main()
