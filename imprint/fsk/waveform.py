from dataclasses import dataclass
from functools import partial
from typing import Callable, Any
import warnings
import numpy as np

def periodic_hann(n):
	return np.hanning(n+1)[:-1]

def default_mod_table(fskw, pattern: int):
	"""Make a table T with size (mod_order, hop_factor)
	To send symbol b at time t, transmit pulse T[b, t%hop_factor].
	"""
	mod_order = 1 << fskw.bits_per_symbol
	sidx = np.arange(mod_order).reshape(-1,1)
	hidx = np.arange(fskw.hop_factor)
	return  (fskw.hop_factor*sidx) + ((pattern*hidx) % fskw.hop_factor)
	
@dataclass
class FSKParameters:
	bits_per_symbol: int = 1
	fs_Hz: float = 44100.0
	fc_Hz: float = 16500.0
	symbol_rate_Hz: float = (44100.0/128.0)
	bw_Hz: float = 3000.0
	hop_factor: int = 63
	mod_table_fn: Callable[[Any], Any] = partial(default_mod_table, pattern=16)
	pulse_window_fn: Callable[[int], np.ndarray] = periodic_hann

class FSKWaveform:
	"""FSK waveform according to design_notes.md
	Populates:
		- wf.mod_table; (mod_order,hop_factor)
		- wf.pulses_cos, wf.pulses_sin; (n_pulses,spp) strangeness in loudspeaker playback might mangle the phase of our pulses, so both I/Q might be needed for energy detection.
	"""
	def __init__(self, fskp: FSKParameters = FSKParameters()):
		self.__dict__.update(fskp.__dict__)
		self.mod_order = 1 << self.bits_per_symbol
		spp_float = self.fs_Hz/self.symbol_rate_Hz
		spp = int(round(spp_float))
		self.samples_per_pulse = spp
		if not (np.abs(spp - spp_float) < 1e-3):
			warnings.warn("Symbol rate isn't a fraction of the sample rate.")
		self.pulse_window = self.pulse_window_fn(spp)
		self.n_pulses = self.mod_order * self.hop_factor
		self.make_pulse_bank()
		self.mod_table = self.mod_table_fn(self)

	def make_pulse_bank(self):
		spp = self.samples_per_pulse
		self.pulses_cos = np.empty([self.n_pulses,spp])
		self.pulses_sin = np.empty([self.n_pulses,spp])
		ts = np.arange(spp)/self.fs_Hz # Time steps in a pulse
		f_start_Hz = self.fc_Hz - self.bw_Hz/2
		fd_Hz = self.bw_Hz/(self.hop_factor*self.mod_order)
		for ipulse in range(self.n_pulses):
			tone_Hz = f_start_Hz + ipulse*fd_Hz
			tone_cos = np.cos(2*np.pi*ts*tone_Hz)
			tone_sin = np.sin(2*np.pi*ts*tone_Hz)
			tone_cos_win = tone_cos*self.pulse_window
			tone_sin_win = tone_sin*self.pulse_window
			g = np.sqrt(spp)/np.sum(tone_cos_win**2 + tone_sin_win**2) # Normalize to unit average power per sample
			self.pulses_cos[ipulse,:] = tone_cos_win*g
			self.pulses_sin[ipulse,:] = tone_sin_win*g

	def bits_to_symbols(self, bits):
		bpsym = self.bits_per_symbol
		pad_len = (-len(bits)) % bpsym
		bits_padded = np.pad(bits, (0,pad_len), constant_values=0)
		syms_binary = bits_padded.reshape(-1, bpsym)
		return syms_binary.dot(1 << np.arange(bpsym))

	def symbols_to_bits(self,syms):
		bits = ((syms[:, None] & (1 << np.arange(self.bits_per_symbol))) > 0).astype(int)
		bits = np.fliplr(bits)
		return bits.ravel()

	def modulate_frame(self, bits):
		syms = self.bits_to_symbols(bits)
		mod_table_col_idx = np.arange(len(syms)) % self.hop_factor
		pidx = self.mod_table[syms, mod_table_col_idx]
		syms_modulated = self.pulses_cos[pidx,:]
		return syms_modulated.reshape(-1)

