"""Shared CLI helpers for cicada command-line tools."""
from __future__ import annotations

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
	parser.add_argument("--wf-fc", type=float, default=16500.0, help="Carrier center frequency (Hz).")
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
		bw_Hz=args.wf_bw,
		hop_factor=args.wf_hop_factor,
		symbols_per_frame=args.wf_symbols_per_frame,
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
		symbols_per_frame=wf.symbols_per_frame,
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
