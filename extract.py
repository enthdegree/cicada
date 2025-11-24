''' Pull frames out of output.wav and dump them to frames.csv. '''
import sys, csv, re, numpy as np, soundfile as sf
from functools import partial
from cicada import payload
from cicada.modem import Modem
from cicada.fsk.demodulator import FSKDemodulator, FSKDemodulatorParameters
from cicada.fsk.waveform import FSKParameters, FSKWaveform, default_mod_table 

# Waveform & demod settings
n_code_sym_per_frame = 1024 # must match cicada.modem default LDPC code
discard_thresh = 0 # If we get more than this many non-alphanumeric chars then throw this frame away
wf_params = FSKParameters(
	symbol_rate_Hz=(44100.0/128.0),
	hop_factor=63,
	mod_table_fn=partial(default_mod_table, pattern=16),
)
demod_params = FSKDemodulatorParameters(
	symbols_per_frame=n_code_sym_per_frame, # number of coded symbols per frame
	frame_search_win=1.2, # search window length in # of frames
	frame_search_win_step=0.3, # search window shift length in # of frames
	pulse_frac=8, # fraction of a pulse to use in pulse search
	plot=True) 

if __name__ == "__main__":
	in_wav = sys.argv[1] if len(sys.argv) > 1 else "output.wav"
	out_csv = sys.argv[2] if len(sys.argv) > 2 else "frames.csv"

	# Construct modem
	wf = FSKWaveform(wf_params)
	demod = FSKDemodulator(cfg=demod_params, wf=wf)
	modem = Modem(wf, demodulator=demod, use_ldpc=True)

	print(f"Searching for frames in {in_wav}...")
	in_sam, fs = sf.read(in_wav, dtype="float32", always_2d=False)
	if in_sam.ndim > 1: in_sam = in_sam.mean(axis=1)
	l_frames, l_frame_start_idx = modem.recover_bytes(in_sam)

	print(f"Recovered {len(l_frames)} frames from {in_wav}, trying to decode...")
	l_payloads = []
	l_payload_start_sam = []
	for iframe in range(len(l_frames)): 
		frame = l_frames[iframe]
		pl = payload.SignaturePayload.from_bytes(frame)
		msg = pl.header.message
		n_non_ascii = sum(1 for ch in msg if ord(ch) > 127)
		if(n_non_ascii <= discard_thresh):
			l_payloads.append(pl)
			l_payload_start_sam.append(l_frame_start_idx[iframe])
			print(f"\nFrame {iframe} contains a good payload:")
			pl.print()
		
	# Write payloads to CSV
	payload.SignaturePayload.write_csv(
		l_payloads,
		l_sam_idx=l_payload_start_sam,
		out_csv=out_csv)
	print(f"Wrote {len(l_payloads)} payloads to {out_csv}")
