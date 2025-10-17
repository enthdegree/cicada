// fsk.js
// Hopped FSK per README and wf.py (Python). Real pulses, precomputed, hopped mapping.
// Defaults: M=1, P=160, N=2, F=69 (19–20.1 kHz @ 44.1 kHz).

export class FSKWaveformJS {
  constructor({ M=1, P=160, N=2, F=69, fs=44100, window='hann' } = {}) {
    this.M=M; this.P=P; this.N=N; this.F=F; this.fs=fs; this.window=window;
    this.Q = 1 << M;
    if (!(0 <= F && F < Math.floor(P/2))) throw new Error(`F out of range for P: F=${F}, P=${P}`);
    const numBins = this.Q * this.N;
    if (F + numBins > Math.floor(P/2)) throw new Error(`Occupied band exceeds Nyquist: F+Q*N=${F+numBins}, P/2=${Math.floor(P/2)}`);
    this.win = (window === 'hann') ? this._hann(P) : this._rect(P);
    this.binIndices = new Int32Array(numBins);
    for (let k=0;k<numBins;k++) this.binIndices[k] = F + k;
    this.pulses = new Array(numBins);
    const n = new Float64Array(P); for (let i=0;i<P;i++) n[i]=i;
    for (let k=0;k<numBins;k++) {
      const fbin = this.binIndices[k];
      const pulse = new Float32Array(P);
      let norm = 0.0;
      for (let i=0;i<P;i++) {
        const v = this.win[i] * Math.cos(2*Math.PI*fbin*n[i]/P);
        pulse[i] = v;
        norm += v*v;
      }
      norm = Math.sqrt(norm) || 1.0;
      for (let i=0;i<P;i++) pulse[i] /= norm;
      this.pulses[k] = pulse;
    }
  }
  _hann(P){
    const w = new Float32Array(P);
    for (let n=0;n<P;n++) w[n] = 0.5 - 0.5*Math.cos(2*Math.PI*n/(P-1));
    return w;
  }
  _rect(P){ return new Float32Array(Array(P).fill(1)); }
  hopIndex(d, t){ const b = t % this.N; return b*this.Q + (d & (this.Q-1)); }
  modulateBits(bits){
    const Lsym = Math.ceil(bits.length / this.M); // with M=1 equals bits length
    const out = new Float32Array(Lsym * this.P);
    for (let t=0;t<Lsym;t++){
      const d = bits[t] & 1;
      const pulse = this.pulses[this.hopIndex(d, t)];
      out.set(pulse, t*this.P);
    }
    return out;
  }
}
