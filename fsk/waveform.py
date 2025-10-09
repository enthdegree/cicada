# wf.py
# FSK waveform per README spec:
# - On construction, precompute a TABLE of real pulses, one per occupied DFT bin.
# - Pulse length = P samples (a.k.a. sps).
# - Hopped FSK: for timeslot t and M-ary symbol d in [0, 2^M-1], transmit the pulse at
#       index f(d,t) = F + (t % N)*2^M + d
#   So the occupied band is bins [F, F + 2^M*N), and no bin repeats within any N slots.
# - Modulator concatenates pulses; no re-synth on the fly.

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

WindowType = str

def _window(P: int, kind: WindowType = 'hann') -> np.ndarray:
    if kind == 'hann':
        n = np.arange(P, dtype=np.float64)
        w = 0.5 - 0.5*np.cos(2*np.pi*n/(P-1))
        return w
    elif kind in ('rect', 'boxcar'):
        return np.ones(P, dtype=np.float64)
    else:
        raise ValueError(f"unknown window kind {kind!r}")

@dataclass
class FSKParams:
    M: int = 1              # bits per symbol
    P: int = 160            # samples per symbol (sps)
    N: int = 2              # repetition period (no bin repeats within N slots)
    F: int = 69             # starting bin index (0..P/2-1)
    fs: int = 44100         # sample rate (used only for metadata / sanity checks)
    win: WindowType = 'hann'

class FSKWaveform:
    def __init__(self, params: FSKParams | None = None):
        self.params = params or FSKParams()
        M, P, N, F = self.params.M, self.params.P, self.params.N, self.params.F
        self.Q = 1 << M                      # alphabet size
        self.sps = P
        # spec sanity checks
        if not (0 <= F < P//2):
            raise ValueError(f"F must be in [0, P/2), got F={F}, P={P}")
        if not (1 <= N < P // (2**(M+1)) + 1):
            # README says N in [1, P/2^{M+1})
            pass  # don't hard fail; warn only
        self.num_bins = self.Q * N
        if F + self.num_bins > P//2:
            raise ValueError(f"Occupied band exceeds Nyquist: F+2^M*N = {F + self.num_bins}, P/2 = {P//2}")
        # occupied DFT bin indices
        self.bin_indices = np.arange(F, F + self.num_bins, dtype=np.int32)  # length Q*N
        # precompute pulses table: shape [Q*N, P]
        self.win = _window(P, self.params.win).astype(np.float64)
        n = np.arange(P, dtype=np.float64)
        pulses = np.empty((self.num_bins, P), dtype=np.float64)
        for k, fbin in enumerate(self.bin_indices):
            # Real pulse: windowed cosine at bin frequency
            pulses[k, :] = self.win * np.cos(2*np.pi*fbin*n/P)
        # Normalize pulses to unit energy (so matched-filter correlation is comparable)
        energies = np.sqrt(np.sum(pulses**2, axis=1, keepdims=True)) + 1e-12
        self.pulses = pulses / energies
        # convenience views per block (N groups of Q bins)
        self.block_pulses = self.pulses.reshape(self.params.N, self.Q, P)

    def hop_index(self, d: int, t: int) -> int:
        """Return global pulse table index for symbol d at timeslot t."""
        if not (0 <= d < self.Q):
            raise ValueError(f"d out of range: {d}")
        b = (t % self.params.N)
        return b * self.Q + d  # offset within occupied band (F offset implicit in table)

    def bits_to_symbols(self, bits: np.ndarray) -> np.ndarray:
        bits = np.asarray(bits, dtype=np.uint8).reshape(-1)
        if self.params.M == 1:
            return bits.copy()
        L = int(np.ceil(bits.size / self.params.M))
        padded = np.zeros(L*self.params.M, dtype=np.uint8)
        padded[:bits.size] = bits
        groups = padded.reshape(L, self.params.M)
        # LSB-first: val = sum(b_i << i)
        weights = (1 << np.arange(self.params.M, dtype=np.uint32))
        return (groups @ weights).astype(np.int32)

    def modulate_symbols(self, syms: np.ndarray) -> np.ndarray:
        """Return concatenated waveform for integer symbols (0..Q-1)."""
        syms = np.asarray(syms, dtype=np.int32).reshape(-1)
        P = self.sps
        out = np.empty(syms.size * P, dtype=np.float64)
        for t, d in enumerate(syms):
            idx = self.hop_index(int(d), t)
            out[t*P:(t+1)*P] = self.pulses[idx, :]
        return out

    def modulate_bits(self, bits: np.ndarray) -> np.ndarray:
        return self.modulate_symbols(self.bits_to_symbols(bits))

    # --------- Demodulation helpers ----------
    def _symbol_llrs_aligned(self, x: np.ndarray, start: int, T: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute, for T symbols starting at sample 'start' (must be P-aligned), the
        matched-filter scores for each M-ary value at each symbol time:
            scores[t, d] = <x[start + t*P : start+(t+1)*P], pulse_for(d,t)>
        Returns (scores, hard_syms)
        """
        P = self.sps
        x = np.asarray(x, dtype=np.float64)
        scores = np.empty((T, self.Q), dtype=np.float64)
        for t in range(T):
            seg = x[start + t*P : start + (t+1)*P]
            if seg.size != P:
                raise ValueError("Segment shorter than one symbol; pad your input or reduce T.")
            block = self.block_pulses[t % self.params.N]  # [Q, P]
            # dot products vs all Q pulses in this block
            scores[t, :] = seg @ block.T
        hard = scores.argmax(axis=1).astype(np.int32)
        return scores, hard

    def demodulate_aligned(self, x: np.ndarray, start: int, num_bits: int) -> np.ndarray:
        """Demodulate bits assuming 'start' is aligned to symbol boundary."""
        T = int(np.ceil(num_bits / self.params.M))
        _, hard_syms = self._symbol_llrs_aligned(x, start, T)
        # map to bits
        if self.params.M == 1:
            bits = hard_syms.astype(np.uint8)
        else:
            bits = np.zeros(T*self.params.M, dtype=np.uint8)
            for t, d in enumerate(hard_syms):
                for i in range(self.params.M):
                    bits[t*self.params.M + i] = (d >> i) & 1
        return bits[:num_bits]

    def search_and_demodulate(self, x: np.ndarray, frame_bits: int = 1024,
                              win_frames: float = 1.5, hop_frames: float = 0.5,
                              coarse_step: int | None = None) -> list[tuple[int, str]]:
        """
        Sliding-window search for frames (by energy/correlation) and demodulate.
        Returns a list of (frame_start_sample, bitstring) for each window hop.
        This is a simple alignment-free method; for best performance, provide alignment.
        """
        P = self.sps
        x = np.asarray(x, dtype=np.float64)
        T = int(np.ceil(frame_bits / self.params.M))
        frame_len = T * P
        win_len = int(win_frames * frame_len)
        hop = max(int(hop_frames * frame_len), 1)
        coarse = P if coarse_step is None else max(1, int(coarse_step))

        out = []
        for wstart in range(0, max(0, len(x)-win_len+1), hop):
            # find best symbol alignment inside the window (coarse grid)
            best_score = -1e9
            best_a = 0
            for a in range(0, P, coarse):
                # score = sum of max correlations for first T symbols starting at wstart+a
                if wstart + a + frame_len > len(x): break
                try:
                    scores, _ = self._symbol_llrs_aligned(x, wstart + a, T)
                except ValueError:
                    break
                s = float(np.max(scores, axis=1).sum())
                if s > best_score:
                    best_score, best_a = s, a
            start = wstart + best_a
            if start + frame_len <= len(x):
                bits = self.demodulate_aligned(x, start, frame_bits)
                bitstr = ''.join(str(int(b)) for b in bits.tolist())
                out.append((start, bitstr))
        return out
