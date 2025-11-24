"""Shared CLI helpers for cicada command-line tools."""

import argparse
from argparse import ArgumentParser, HelpFormatter
from functools import partial
from pathlib import Path
import blst

from cicada.fsk.waveform import FSKParameters, FSKWaveform, default_mod_table
from cicada.fsk.demodulator import FSKDemodulatorParameters, FSKDemodulator
from cicada.modem import Modem
from cicada.payload import payload_type_choices

DEFAULT_OUT_DIR = Path("out")

class WrappedHelpFormatter(HelpFormatter):
	def __init__(self, prog, width=80, max_help_position=26):
		super().__init__(prog, width=width, max_help_position=max_help_position)

def ensure_output_dir(path: Path | str | None) -> Path:
	out = Path(path) if path else DEFAULT_OUT_DIR
	out.mkdir(parents=True, exist_ok=True)
	return out

def resolve_output_path(out_dir: Path, target: Path | str) -> Path:
	target_path = Path(target)
	if target_path.is_absolute():
		return target_path
	return out_dir / target_path

def add_output_dir_arg(parser: ArgumentParser):
	parser.add_argument(
		"--out-dir",
		type=Path,
		default=DEFAULT_OUT_DIR,
		help=f"Directory for generated files (default: %(default)s)",
	)

def add_debug_flag(parser: ArgumentParser):
	parser.add_argument(
		"--debug",
		action="store_true",
		default=False,
		help="Enable verbose debug logging",
	)

def add_waveform_args(parser: ArgumentParser):
	parser.add_argument("--wf-bits-per-symbol", type=int, default=1, help="Number of bits per FSK symbol.")
	parser.add_argument("--wf-fs", type=float, default=44100.0, help="Sample rate (Hz).")
	parser.add_argument("--wf-fc", type=float, default=17500.0, help="Carrier center frequency (Hz).")
	parser.add_argument("--wf-symbol-rate", type=float, default=(44100.0 / 128.0), help="Symbol rate (Hz).")
	parser.add_argument("--wf-bw", type=float, default=3000.0, help="Waveform bandwidth (Hz).")
	parser.add_argument("--wf-hop-factor", type=int, default=63, help="Frequency hop factor.")
	parser.add_argument("--wf-symbols-per-frame", type=int, default=1024, help="Symbols per frame (used by modem/demod).")
	parser.add_argument("--wf-mod-pattern", type=int, default=16, help="Pattern multiplier for modulation table.")

def build_waveform_parameters(args) -> FSKParameters:
	return FSKParameters(
		bits_per_symbol=args.wf_bits_per_symbol,
		fs_Hz=args.wf_fs,
		fc_Hz=args.wf_fc,
		symbol_rate_Hz=args.wf_symbol_rate,
		symbols_per_frame=args.wf_symbols_per_frame,
		bw_Hz=args.wf_bw,
		hop_factor=args.wf_hop_factor,
		mod_table_fn=partial(default_mod_table, pattern=args.wf_mod_pattern),
	)

def add_demod_args(parser: ArgumentParser):
	parser.add_argument("--demod-frame-search-win", type=float, default=1.2, help="Frame search window length (frames).")
	parser.add_argument("--demod-frame-search-step", type=float, default=0.4, help="Frame search window step (frames).")
	parser.add_argument("--demod-pulse-frac", type=int, default=8, help="Fraction of a pulse length to use in frame search; higher = finer search.")
	parser.add_argument("--demod-highpass", type=int, default=8, help="High-pass filter length for frame demod (pulses).")
	parser.add_argument(
		"--demod-plot",
		dest="demod_plot",
		action="store_true",
		help="Enable demodulator plots (saved to out-dir).",
	)
	parser.add_argument(
		"--demod-no-plot",
		dest="demod_plot",
		action="store_false",
		help="Disable demodulator plots.",
	)
	parser.set_defaults(demod_plot=True)

def build_demodulator_parameters(args, wf: FSKWaveform) -> FSKDemodulatorParameters:
	return FSKDemodulatorParameters(
		frame_search_win=args.demod_frame_search_win,
		frame_search_win_step=args.demod_frame_search_step,
		pulse_frac=args.demod_pulse_frac,
		high_pass_len_pulses=args.demod_highpass,
		plot=args.demod_plot,
	)

def add_modem_flags(parser: ArgumentParser):
	parser.add_argument(
		"--no-ldpc",
		dest="use_ldpc",
		action="store_false",
		help="Disable LDPC coding.",
	)
	parser.add_argument(
		"--ldpc",
		dest="use_ldpc",
		action="store_true",
		help="Enable LDPC coding.",
	)
	parser.add_argument(
		"--keep-duplicates",
		dest="discard_duplicate_frames",
		action="store_false",
		help="Do not discard duplicate frames detected by the demodulator.",
	)
	parser.set_defaults(discard_duplicate_frames=True)
	parser.set_defaults(use_ldpc=True)

# ---- Command-specific parser builders ----
def build_sign_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Continuously transcribe mic audio and transmit payload frames.",
		formatter_class=lambda prog: WrappedHelpFormatter(prog, width=80),
	)
	add_output_dir_arg(parser)
	add_debug_flag(parser)
	add_payload_type_arg(parser)
	add_waveform_args(parser)
	add_demod_args(parser)
	add_modem_flags(parser)
	parser.add_argument("--model-size", default="medium.en", help="Whisper model size.")
	parser.add_argument("--window-sec", type=float, default=10.0, help="Transcription window length (s).")
	parser.add_argument("--overlap-sec", type=float, default=5.0, help="Transcription window overlap (s).")
	parser.add_argument("--mic-blocksize", type=int, default=1024, help="Audio blocksize for microphone capture.")
	parser.add_argument(
		"--signer-transcript",
		type=Path,
		nargs="?",
		const=Path("signer_transcript.md"),
		default=None,
		help="Optional path to log raw transcript chunks (default: out/signer_transcript.md).",
	)
	parser.add_argument("--header-message", default="q3q.net", help="Header message for SignaturePayloads.")
	parser.add_argument("--bls-privkey", type=Path, default=Path("bls_privkey.bin"), help="Path to BLS private key.")
	parser.add_argument("--bls-pubkey", type=Path, default=Path("bls_pubkey.bin"), help="Path to BLS public key.")
	return parser

def build_extract_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Demodulate frames from a WAV file and write them to CSV.",
		formatter_class=lambda prog: WrappedHelpFormatter(prog, width=80),
	)
	add_output_dir_arg(parser)
	add_debug_flag(parser)
	add_payload_type_arg(parser)
	add_waveform_args(parser)
	add_demod_args(parser)
	add_modem_flags(parser)
	parser.add_argument("input_wav", type=Path, help="Input WAV file to analyze.")
	parser.add_argument(
		"--output-csv",
		type=Path,
		nargs="?",
		const=None,
		default=None,
		help="Filename (relative to out-dir unless absolute) for extracted payload metadata (default: out/<input>_frames.csv).",
	)
	parser.add_argument(
		"--nonascii-discard-threshold",
		type=int,
		default=0,
		help="Maximum allowed non-ASCII characters allowed in a text field before discarding a payload.",
	)
	return parser

def build_verify_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Verify frames against a transcription.",
		formatter_class=lambda prog: WrappedHelpFormatter(prog, width=80),
	)
	add_output_dir_arg(parser)
	add_debug_flag(parser)
	add_payload_type_arg(parser)
	add_waveform_args(parser)
	add_demod_args(parser)
	add_modem_flags(parser)
	parser.add_argument("input", type=Path, help="Input WAV to transcribe or transcript markdown to verify directly.")
	parser.add_argument(
		"--frames-csv",
		type=Path,
		default=None,
		help="CSV produced by extract.py (default: out/frames.csv).",
	)
	parser.add_argument(
		"--output-md",
		type=Path,
		nargs="?",
		const=None,
		default=None,
		help="Where to write annotated markdown (default: out/<input>_transcript.md).",
	)
	parser.add_argument("--model-size", default="medium.en", help="Whisper model size to use for transcription (signature payloads only).")
	parser.add_argument("--window-sec", type=float, default=10.0, help="Transcription window length in seconds.")
	parser.add_argument("--overlap-sec", type=float, default=8.0, help="Transcription window overlap in seconds.")
	parser.add_argument("--bls-pubkey", type=Path, default=Path("bls_pubkey.bin"), help="BLS public key for SignaturePayload verification.")
	parser.add_argument("--nonascii-discard-threshold", type=int, default=0, help="Max non-ASCII characters allowed in payload content before discarding.")
	return parser

def add_payload_type_arg(parser: ArgumentParser, default: str = "signature"):
	choices = payload_type_choices()
	default_choice = default if default in choices else (choices[0] if choices else default)
	parser.add_argument(
		"--payload-type",
		choices=choices,
		default=default_choice,
		help="Choose whether frames carry BLS SignaturePayloads or PlaintextPayloads.",
	)

def build_modem(args, plot_dir: Path):
	wf = FSKWaveform(build_waveform_parameters(args))
	demod_params = build_demodulator_parameters(args, wf)
	demod = FSKDemodulator(cfg=demod_params, wf=wf, plot_dir=plot_dir)
	modem = Modem(wf, demodulator=demod, discard_duplicate_frames=args.discard_duplicate_frames, use_ldpc=args.use_ldpc, use_bit_mask=False)
	return modem, wf, demod

def load_bls_keypair(priv_path: Path, pub_path: Path):
	with open(priv_path, "rb") as f:
		priv_bytes = f.read()
	with open(pub_path, "rb") as f:
		pub_bytes = f.read()
	secret = blst.SecretKey()
	secret.from_bendian(priv_bytes)
	return secret, pub_bytes

def load_bls_pubkey(pub_path: Path) -> bytes:
	with open(pub_path, "rb") as f:
		return f.read()
