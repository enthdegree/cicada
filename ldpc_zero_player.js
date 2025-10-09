// ldpc_zero_player.js
// Plays an LDPC-coded (n=1024,k=512) frame of zeros over hopped FSK around ~19–20 kHz.
// Requires: ldpc_encoder_simple.js (Encoder1024R12).
// Serve via http:// (not file://).

import { Encoder1024R12 } from './ldpc_encoder_simple.js';

class FSKWaveformJS {
  // Matches README spec and Python wf.FSKWaveform defaults: M=1, P=160, N=2, F=69, fs=44100, hann window.
  constructor({ M=1, P=160, N=2, F=69, fs=44100, window='hann' } = {}) {
    this.M=M; this.P=P; this.N=N; this.F=F; this.fs=fs; this.window=window;
    this.Q = 1 << M;
    if (!(0 <= F && F < Math.floor(P/2))) throw new Error(`F out of range for P: F=${F}, P=${P}`);
    const numBins = this.Q * this.N;
    if (F + numBins > Math.floor(P/2)) throw new Error(`Occupied band exceeds Nyquist: F+Q*N=${F+numBins}, P/2=${Math.floor(P/2)}`);
    // Build window
    this.win = (window === 'hann') ? this._hann(P) : this._rect(P);
    // Precompute pulses table for bins [F, F+Q*N)
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

  hopIndex(d, t){
    if (d<0 || d>=this.Q) throw new Error('symbol d out of range');
    const b = t % this.N;
    return b*this.Q + d;
  }

  modulateBits(bits){
    // bits: Uint8Array of 0/1, length Lbits
    const Lsym = Math.ceil(bits.length / this.M); // with M=1 this equals bits.length
    const out = new Float32Array(Lsym * this.P);
    for (let t=0;t<Lsym;t++){
      const d = bits[t] & 1; // M=1
      const idx = this.hopIndex(d, t);
      const pulse = this.pulses[idx];
      out.set(pulse, t*this.P);
    }
    return out;
  }
}

export class LDPCZeroPlayer {
  constructor(audioCtx, {frameEverySec=5, ebn0db=null} = {}) {
    this.ctx = audioCtx || new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 });
    this.enc = new Encoder1024R12(); // n=1024, k=512
    this.fsk = new FSKWaveformJS({ M:1, P:160, N:2, F:69, fs:this.ctx.sampleRate });
    this.timer = null;
    this.periodSec = frameEverySec;
    this.ebn0db = ebn0db; // if set, add AWGN in baseband before playback (educational)
  }

  _awgn(samples, ebn0db){
    // crude AWGN assuming BPSK-like symbol energy ~1; just for demo
    const out = samples.slice();
    const R = 0.5; // rate
    const esn0db = ebn0db + 10*Math.log10(R);
    const esn0 = Math.pow(10, esn0db/10);
    const sigma2 = 1/(2*esn0);
    const sigma = Math.sqrt(sigma2);
    for (let i=0;i<out.length;i++){
      out[i] += sigma * (Math.random()*2-1); // uniform approx; fine for demo
    }
    return out;
    }

  _frameZeros(){
    // Make k=512 zeros, encode to 1024 code bits, modulate to audio samples (Float32Array)
    const u = new Uint8Array(this.enc.K); // zeros
    const cw = this.enc.encode(u);        // length 1024, [u|p]
    const samples = this.fsk.modulateBits(cw);
    return samples;
  }

  _playBuffer(samples){
    const buf = this.ctx.createBuffer(1, samples.length, this.ctx.sampleRate);
    buf.copyToChannel(samples, 0);
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.ctx.destination);
    src.start();
  }

  playOnce(){
    let s = this._frameZeros();
    if (typeof this.ebn0db === 'number') s = this._awgn(s, this.ebn0db);
    this._playBuffer(s);
  }

  start(){
    if (this.timer) return;
    this.playOnce();
    this.timer = setInterval(()=>this.playOnce(), this.periodSec*1000);
  }
  stop(){
    if (!this.timer) return;
    clearInterval(this.timer);
    this.timer = null;
  }
}
