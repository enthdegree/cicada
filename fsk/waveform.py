from dataclasses import dataclass
from functools import partial
import numpy as np

def periodic_hann(n):
	return np.hanning(n+1)[:-1]

def default_mod_table(fskp: FSKParams, p: int):
	"""Make a table T with size (mod_order, hop_factor)
	To send symbol b at time t, transmit pulse T[b, t%hop_factor].
	"""
	mod_order = 1 << fskp.bits_per_symbol
	sidx = np.arange(mod_order).reshape(-1,1)
	hidx = np.arange(fskp.hop_factor)
	return  (fskp.hop_factor*sidx) + ((p*hidx) % fskp.hop_factor)
	
@dataclass
class FSKParams:
	"""FSK parameters, according to design_notes.md 
	"""
	bits_per_symbol: int = 1
	fs_Hz: float = 44100.0
	fc_Hz: float = 18500.0
	symbol_rate_Hz: float = 344.5
	bw_Hz: float = 3000.0
	hop_factor: int = 63
	mod_table_function: partial(default_mod_table, pattern=16)
	pulse_window_function: periodic_hann

class FSKWaveform:
	"""FSK waveform according to design_notes.md
	Populates:
		- wf.mod_table; (mod_order,hop_factor)
		- wf.pulses_cos, wf.pulses_sin; (n_pulses,spp) strangeness in loudspeaker playback might mangle the phase of our pulses, so both I/Q might be needed for energy detection.
	"""
	def __init__(self, p: FSKParams):
		self.p = p
		self.mod_order = 1 << p.bits_per_symbol
		spp = int(round(p.fs_Hz/p.symbol_rate_Hz))
		self.samples_per_pulse = spp
		if np.abs(spp - p.fs_Hz/p.symbol_rate_Hz) > 1e-3:
			warnings.warn("Symbol rate isn't a fraction of the sample rate.")
		self.pulse_window = p.pulse_window_function(spp)
		self.n_pulses = self.mod_order * p.hop_factor
		self.make_pulse_bank(self)
		self.mod_table = self.mod_table_function(p)

	def make_pulse_bank(self):
		spp = self.samples_per_pulse
		self.pulses_cos = np.empty([self.n_pulses,spp])
		self.pulses_sin = np.empty([self.n_pulses,spp])
		ts = np.arange(spp)/self.p.fs_Hz # Time steps in a pulse
		f_start_Hz = self.p.fc_Hz - self.p.bw_Hz/2
		fd_Hz = self.p.bw_Hz/(self.p.hop_factor*self.mod_order)
		for ipulse in range(self.n_pulses):
			tone_Hz = self.f_start_Hz + ipulse*fd_Hz
			tone_cos = np.cos(2*np.pi*ts*tone_Hz)
			tone_sin = np.sin(2*np.pi*ts*tone_Hz)
			self.pulses_cos[ipulse,:] = tone_cos*self.pulse_window
			self.pulses_sin[ipulse,:] = tone_sin*self.pulse_window

	def bits_to_symbols(self, bits):
		pad_len = (-len(bits)) % self.bits_per_symbol
		bits_padded = np.pad(bits, (0,pad_len), constant_values=0)
		syms_binary = bits_padded.reshape(-1, self.bits_per_symbol)
		return syms_binary.dot(1 << np.arange(self.bits_per_symbol))

	def symbols_to_bits(self,syms):
		bits = ((syms[:, None] & (1 << np.arange(self.bits_per_symbol))) > 0).astype(int)
		bits = np.fliplr(bits)
		return bits.ravel()

	def modulate_frame(self, bits):
		syms = self.bits_to_symbols(bits)
		t = np.arange(len(syms)) % self.wf.hop_factor
		pidx = self.hop_table[syms, t]
		frames = self.pulses_cos[pidx,:]
		return frames.reshape(-1)

