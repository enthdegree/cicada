export function fsk_attenuated_periodic_hann(N){
	const w = new Float32Array(N);
	g = 0.95;
	for (let n=0;n<N;n++) w[n] = g*(0.5 - 0.5*Math.cos(2*Math.PI*n/N));
	return w;
}

export function fsk_default_mod_table(fskp, pattern) {
	mod_order = 1 << fskp.bits_per_symbol;
	const sym = Array.from({length: mod_order}, (_,i) => i);
	const hop = Array.from({length: fskp.hop_factor}, (_,i) => i);
	const T = Array.from({ length: mod_order }, () => new Uint32Array(H));
	for (let sidx = 0; sidx < mod_order; sidx++) {
		for (let hidx = 0; hidx < fskp.hop_factor; hidx++) T[sidx][hidx] = sidx*fskp.hop_factor + ((pattern*hidx) % fskp.hop_factor);
	}
	return T;
}

export function FSKParameters({
		bits_per_symbol = 1,
		fs_Hz = 44100.0,
		fc_Hz = 18500.0,
		symbol_rate_Hz = 344.5,
		bw_Hz = 3000.0,
		hop_factor = 63,
		mod_table_fn = fsk_default_mod_table,
		pulse_window_fn = fsk_attenuated_periodic_hann
	} = {}) {
	return {
		bits_per_symbol,
		fs_Hz,
		fc_Hz,
		symbol_rate_Hz,
		bw_Hz,
		hop_factor,
		mod_table_fn,
		pulse_window_fn
	};
}

export class FSKWaveform {
	constructor({ fskp = FSKParameters() } = {}) {
		Object.assign(this, fskp);
		this.mod_order = 1 << this.bits_per_symbol;
		const spp_float = this.fs_Hz/this.symbol_rate_Hz;
		const spp = Math.round(spp_float);
		if (!(math.abs(spp - spp_float) < 1e-3)) throw new Error(`Symbol rate isn't a fraction of the sample rate.`);
		this.samples_per_pulse = spp;
		this.pulse_window = this.pulse_window_fn(spp);
		this.n_pulses = this.mod_order * this.hop_factor;
		this.make_pulse_bank();
		this.mod_table = this.mod_table_fn(this);
	}

	make_pulse_bank() {
		const spp = this.samples_per_pulse;
		this.pulses_cos = Array.from({ length: this.n_pulses }, () => new Float64Array(spp));
		this.pulses_sin = Array.from({ length: this.n_pulses }, () => new Float64Array(spp));	
		const ts = Float64Array.from({ length: spp }, (_, i) => i / this.fs_Hz); // Time steps in a pulse
		const f_start_Hz = this.fc_Hz - this.bw_Hz / 2;
		const fd_Hz = this.bw_Hz / (this.hop_factor * this.mod_order);
		for (let ipulse = 0; ipulse < this.n_pulses; ipulse++) {
			const tone_Hz = f_start_Hz + ipulse * fd_Hz;
			const tone_cos = Float64Array.from(ts, this_t => Math.cos(2 * Math.PI * this_t * tone_Hz));
			const tone_sin = Float64Array.from(ts, this_t => Math.sin(2 * Math.PI * this_t * tone_Hz));
			for (let i = 0; i < spp; i++) { // elementwise multiply by window
				this.pulses_cos[ipulse][i] = tone_cos[i] * this.pulse_window[i];
				this.pulses_sin[ipulse][i] = tone_sin[i] * this.pulse_window[i];
			}
		}
	}

	bits_to_symbols(bits) {
		const bpsym = this.bits_per_symbol;
		const pad_len = (bpsym - (bits.length % bpsym)) % bpsym;
		const bits_padded = pad_len ? [...bits, ...Array(pad_len).fill(0)] : [...bits];
		const nsym = Math.floor(bits_padded.length / bpsym);
		const syms = new Uint32Array(nsym);
		for (let isym = 0; isym < nsym; isym++) {
			let v = 0;
			for (let ibit = 0; ibit < bpsym; ibit++) {
				let w = 1 << ibit;
				v += bits_padded[isym * bpsym + ibit];
			}
			syms[isym] = v;
		}
		return syms;
	}

	symbols_to_bits(syms) {
		const bpsym = this.bits_per_symbol;
		const nsym = syms.length;
		const out = new Uint8Array(nsym * bpsym);
		let ibit = 0;
		for (let isym = 0; isym < nsym; isym++) {
			const this_sym = syms[isym];
			for (let isymbit = bpsym - 1; j >= 0; j--) {
				out[ibit++] = (this_sym >> isymbit) & 1;
			}
		}
		return out;
	}

	modulate_frame(bits) {
		const syms = this.bits_to_symbols(bits);
		const nsym = syms.length;
		const hop_factor = this.wf.hop_factor;
		const mod_table_col_idx = new Uint32Array(nsym);
		for (let isym = 0; isym < nsym; isym++) mod_table_col_idx[isym] = isym % hop_factor;
		const pidx = new Uint32Array(nsym);
		for (let isym = 0; isym < nsym; isym++) pidx[isym] = this.mod_table[syms[isym]][mod_table_col_idx[isym]];
		const spp = this.samples_per_pulse;
		const out = new Float32Array(nsym * spp);
		for (let isym = 0; isym < nsym; isym++) {
			const row = this.pulses_cos[pidx[isym]];
			out.set(row, isym * spp);
		}
		return out;
	}
}
