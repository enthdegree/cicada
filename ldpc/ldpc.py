# ldpc/ldpc_simple.py
# Minimal QC-IRA LDPC, n=1024, k=512 (rate 1/2).
# - H = [Hu | Hp], Hp is dual-diagonal of ZxZ circulant permutations (easy, linear-time encoding)
# - No permutations, no GF(2) factorization
# - Decoder: layered normalized min-sum (alpha=0.8), early stopping
#
# Public API:
#   K, N = 512, 1024
#   enc = Encoder(); dec = Decoder()
#   cw = enc.encode(u)                     # u: uint8 array (len K) -> Uint8 codeword (len N)
#   hard, iters, ok = dec.decode(llr)      # llr: float array (len N)

from __future__ import annotations
import numpy as np

# ----- Code parameters -----
Z   = 32
BR  = 16
BC  = 32
M   = BR * Z         # 512 parity checks
N   = BC * Z         # 1024 length
K   = N - M          # 512 info
R   = K / N

ROTS = np.array([1,5,9,13,3,7,11,15,2,6,10,14,4,8,12,16], dtype=np.int32)

def _rot_block_into(src: np.ndarray, s_off: int, dst: np.ndarray, d_off: int, r: int):
    s = r % Z
    if s == 0:
        dst[d_off:d_off+Z] ^= src[s_off:s_off+Z]
        return
    a = src[s_off:s_off+Z]
    dst[d_off:d_off+Z] ^= np.concatenate([a[Z-s:], a[:Z-s]])

def _build_Hu():
    rows = [[] for _ in range(M)]
    info_bc = BC - BR  # 16
    for i in range(BR):
        for t in range(6):  # row degree 6 in info part
            j = (i*3 + t*5) % info_bc
            shift = (11*i + 7*j + 3) % Z
            for z in range(Z):
                r = i*Z + z
                c = j*Z + ((z + shift) % Z)
                rows[r].append(c)
    for r in range(M):
        if len(rows[r]) > 1:
            rows[r] = sorted(set(rows[r]))
    return rows

def _build_H(full=False):
    Hu_rows = _build_Hu()
    if not full:
        return Hu_rows
    rows = [list(Hu_rows[r]) for r in range(M)]
    for i in range(BR):
        j_main = (BC - BR) + i
        j_prev = (BC - BR) + i - 1
        rot = int(ROTS[i])
        for z in range(Z):
            r = i*Z + z
            c_main = j_main*Z + ((z + rot) % Z)
            rows[r].append(c_main)
            if i > 0:
                c_prev = j_prev*Z + z
                rows[r].append(c_prev)
        rows[i*Z:(i+1)*Z] = [sorted(set(rr)) for rr in rows[i*Z:(i+1)*Z]]
    return rows

class Encoder:
    def __init__(self):
        self.Hu_rows = _build_Hu()

    def encode(self, u: np.ndarray) -> np.ndarray:
        u = np.asarray(u, dtype=np.uint8).reshape(-1)
        if u.shape[0] != K:
            raise ValueError(f"u must have length {K}")
        s = np.zeros(M, dtype=np.uint8)
        for r in range(M):
            acc = 0
            for c in self.Hu_rows[r]:
                acc ^= u[c]
            s[r] = acc
        p = np.zeros(M, dtype=np.uint8)
        _rot_block_into(s, 0, p, 0, int(ROTS[0]))
        for i in range(1, BR):
            off = i*Z; prev = (i-1)*Z
            p[off:off+Z] = s[off:off+Z] ^ p[prev:prev+Z]
            _rot_block_into(p, off, p, off, int(ROTS[i]))
        return np.concatenate([u, p]).astype(np.uint8, copy=False)

class Decoder:
    def __init__(self, alpha: float = 0.8, clip: float = 20.0):
        self.alpha = float(alpha); self.clip = float(clip)
        self.rows  = _build_H(full=True)
        self.row2cols = [np.array(rr, dtype=np.int32) for rr in self.rows]
        col2rows = [[] for _ in range(N)]
        for r, cols in enumerate(self.row2cols):
            for c in cols: col2rows[c].append(r)
        self.col2rows = [np.array(rs, dtype=np.int32) for rs in col2rows]
        self.pos_in_row = {}; self.pos_in_col = {}
        for r, cols in enumerate(self.row2cols):
            for i, c in enumerate(cols): self.pos_in_row[(r,c)] = i
        for c, rs in enumerate(self.col2rows):
            for j, r in enumerate(rs): self.pos_in_col[(c,r)] = j
        self.rmsg = [np.zeros(len(cols), dtype=np.float32) for cols in self.row2cols]
        self.Lch  = np.zeros(N, dtype=np.float32)
        self.hard = np.zeros(N, dtype=np.uint8)

    def _syndrome_zero(self, hard: np.ndarray) -> bool:
        for r, cols in enumerate(self.row2cols):
            if (hard[cols].sum() & 1): return False
        return True

    def decode(self, llr, max_iters: int = 60):
        llr = np.asarray(llr, dtype=np.float32).reshape(-1)
        if llr.shape[0] != N: raise ValueError(f"llr must have length {N}")
        self.Lch[:] = llr
        q = [np.full(len(self.col2rows[c]), self.Lch[c], dtype=np.float32) for c in range(N)]
        alpha, CLIP = self.alpha, self.clip

        for it in range(1, max_iters+1):
            for r, cols in enumerate(self.row2cols):
                msgs = np.empty(len(cols), dtype=np.float32)
                for i, c in enumerate(cols): msgs[i] = q[c][ self.pos_in_col[(c,r)] ]
                signs = np.sign(msgs)
                prod_sign = np.prod(signs, dtype=np.float32)
                a = np.abs(msgs)
                m1 = a.min()
                rvals = alpha * prod_sign * (m1 * (np.sign(msgs)))
                rvals = np.clip(rvals, -CLIP, CLIP)
                self.rmsg[r][:] = rvals

                for i, c in enumerate(cols):
                    j = self.pos_in_col[(c, r)]
                    s = 0.0
                    for rr in self.col2rows[c]:
                        s += self.rmsg[rr][ self.pos_in_row[(rr, c)] ]
                    L = self.Lch[c] + s
                    q[c][j] = np.clip(L - self.rmsg[r][ self.pos_in_row[(r, c)] ], -CLIP, CLIP)

            for c in range(N):
                s = 0.0
                for rr in self.col2rows[c]:
                    s += self.rmsg[rr][ self.pos_in_row[(rr, c)] ]
                L = self.Lch[c] + s
                self.hard[c] = 0 if L >= 0 else 1

            if self._syndrome_zero(self.hard):
                return self.hard.copy(), it, True

        return self.hard.copy(), max_iters, False
