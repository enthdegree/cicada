from __future__ import annotations
from dataclasses import dataclass
from logging import warning
import numpy as np
from scipy.signal import medfilt
from numpy.lib.stride_tricks import as_strided
from .waveform import FSKWaveform
import matplotlib.pyplot as plt

@dataclass 
class FSKDemodulatorParameters: 
	symbols_per_frame: int = 1024 # number of coded symbols per frame
	frame_search_win: float = 1.2 # search window length in # of frames
	frame_search_win_step: float = 0.3 # search window shift length in # of frames
	pulse_frac: int = 8 # fraction of a pulse to use in pulse search
	median_window_len_pulses: int = 8
	plot: bool = True

@dataclass 
class FSKDemodulatorResult: # This is a data class that will be produced by frame_search.py
	syms: int # Symbol hard-decisions
	sym_log_likelihoods: np.ndarray # Symbol log-likelihood table; shape (mod_order, symbols_per_frame)
	pulse_map_idx: int = None # Column in the pulse energy map where this frame started 
	start_idx: int = None # Sample index where this frame started
	bit_llrs: np.ndarray = None # Bit log-likelihood ratios; shape (symbols_per_frame * wf.n_bits_per_symbol,)

class FSKDemodulator:
	"""Pulse bank demodulator for FSKWaveform
	"""

	def __init__(self, cfg: FSKDemodulatorParameters = FSKDemodulatorParameters(), wf: FSKWaveform = FSKWaveform()):
		self.__dict__.update(cfg.__dict__)
		self.wf = wf
	
	@staticmethod 
	def _hankel(x: np.ndarray, win: int, step: int = 1) -> np.ndarray:
		"""Strided [win,n] Hankel matrix from x; column i is x[i*step:i*step+win] 
		"""
		if len(x) < win: 
			raise ValueError("Signal shorter than window")
		n = 1+(len(x)-win)//step
		s0 = x.strides[0]
		return as_strided(x, shape=(win,n), strides=(s0, s0*step), writeable=False)

	def pulse_energy_map(self, x: np.ndarray, step: int=1) -> np.ndarray:
		"""Energy map for all pulses over fine time offsets.
		"""
		X = self._hankel(x, self.wf.samples_per_pulse, step=step)
		C = self.wf.pulses_cos @ X
		S = self.wf.pulses_sin @ X
		M = C * C + S * S
		M_eq = M / (np.mean(M, axis=1, keepdims=True)  + 1e-12) # Mic might not be equally sensitive to each pulse
		filtsz = int(self.median_window_len_pulses*self.pulse_frac/2)*2 + 1
		M_base = medfilt(M_eq, kernel_size=(1,filtsz))
		M_filt = M_eq - M_base # Heuristic to mitigate bias from transients and ISI
		return M_eq # M_filt

	def symbol_energy_map(self, Ep: np.ndarray, start: int) -> np.ndarray:
		"""Assuming a frame at col `start` of Ep, gather the frame's symbol
		likelihoods according to the hopping pattern.
		Returns (mod_order, spf)."""
		spf = self.symbols_per_frame
		pfrac = self.pulse_frac
		last_col = start + (spf-1)*pfrac
		if Ep.shape[1] < last_col:
			raise ValueError(f"Tried to search Ep forward to {last_col} but Ep.shape[1]={Ep.shape[1]}")
		isym = np.arange(spf) # (spf,), symbol indices for this frame
		ic = start + isym*pfrac # (spf,), symbol indices for this frame in Ep
		ir = self.wf.mod_table[:, isym % self.wf.hop_factor] # (mod_order,spf)
		return Ep[ir, ic]

	def demodulate_frame(self, Es: np.ndarray, start=0, scale=1) -> FSKDemodulatorResult:
		"""Demodulates a frame given a symbol energy map.
		"""
		start_idx = start * self.pulse_frac
		syms = np.argmax(Es, axis=0)
		mZ = Es / scale
		Zmax = np.max(mZ, axis=0, keepdims=True)
		mP = np.exp(mZ - Zmax) 
		mP /= np.sum(mP, axis=0, keepdims=True) # Normalized symbol probabilities 
		ll = np.log(mP) # Symbol log-likelihoods
		bit_llrs = None
		if(self.wf.bits_per_symbol == 1): bit_llrs = ll[0,:].ravel()-ll[1,:].ravel() 
		else: warning("Only 1-bit-per-symbol demod is supported right now. Skipping bit LLR computation.")
		return FSKDemodulatorResult(pulse_map_idx=start, start_idx=start_idx, syms=syms, sym_log_likelihoods=ll, bit_llrs=bit_llrs)

	def frame_energy_map(self, Ep: np.ndarray) -> np.ndarray:
		"""Given a map of pulse energies, find the vector Ef where Ef[i] is 
		the max-likelihood frame energy assuming it started at col `start` of Ep.
		"""
		sym_per_f = self.symbols_per_frame
		pfrac = self.pulse_frac
		n_off = int(np.floor( Ep.shape[1] / (sym_per_f*pfrac) - 1 )*(sym_per_f*pfrac)+1)
		Ef = np.empty(n_off)
		for ic in range(n_off):
			Es = self.symbol_energy_map(Ep,ic)
			Ef[ic] = np.sum(np.max(Es,axis=0))
		return Ef

	def frame_search(self, x: np.ndarray) -> list[FSKDemodulatorResult]:
		"""Search for and demodulate frames in a sample vector.
		"""
		pfrac = self.pulse_frac
		step = int(round(self.wf.samples_per_pulse / pfrac))
		Ep = self.pulse_energy_map(x, step=step) 
		Ef = self.frame_energy_map(Ep) 
		spf = self.symbols_per_frame
		win_len_cols = int(round(self.frame_search_win * spf * pfrac))
		win_step_cols = int(round(self.frame_search_win_step * spf * pfrac))
		l_dr = []
		l_starts = []
		for s in range(0, max(0, len(Ef) - win_len_cols + 1), win_step_cols):
			start = s + np.argmax(Ef[s:s+win_len_cols])
			l_starts.append(start)
		l_starts = list(set(l_starts))
		l_starts.sort()
		for start in l_starts:
			Es = self.symbol_energy_map(Ep, start)
			dr = self.demodulate_frame(Es, start)
			l_dr.append(dr)

		if self.plot:
			lo = np.percentile(Ep, 10)
			hi = np.percentile(Ep, 90)
			plt.figure(figsize=(32,4)) # Ep: 2D energy vs time
			plt.imshow(
				Ep-np.mean(Ep,axis=0, keepdims=True),
				aspect="auto",
				vmin=lo,
				vmax=hi,
				origin="lower",
			)
			for dr in l_dr: # Line markers for detected frames
				plt.axvline(dr.pulse_map_idx, color="red", linestyle="--", linewidth=0.8)
			plt.colorbar(label="energy")
			plt.title("Ep (pulse energy map)")
			plt.xlabel("time col / sample offset (strided)")
			plt.ylabel("pulse / hop")
			plt.savefig("pulse_energy.png", dpi=300, bbox_inches="tight")

			plt.figure(figsize=(32,4)) # Ef: 1D frame energy
			plt.plot(Ef)
			for dr in l_dr: # Line markers for detected frames
				plt.axvline(dr.pulse_map_idx, color="red", linestyle="--", linewidth=1.8)
			plt.title("Ef (frame energy)")
			plt.xlabel("start col")
			plt.ylabel("score")
			plt.savefig("frame_energy.png", dpi=300, bbox_inches="tight")

		return l_dr, Ef, Ep

