"""	
1. Transcribe a wav to English
2. Look for data frames in the wav
3. Match the data frames (assumed to contain Payloads) to the Step 1 transcription 
4. Annotate the Step 1 transcription with matches
"""
from functools import partial
import sys
from math import gcd
from cicada import speech, payload, verification
from cicada.fsk.demodulator import FSKDemodulator, FSKDemodulatorParameters
from cicada.fsk.waveform import FSKParameters, FSKWaveform, default_mod_table
from faster_whisper import WhisperModel

debug = True 

# BLS key settings
bls_pubkey_file = "./bls_pubkey.bin"

# Whisper speech model settings
window_sec = 10.0
overlap_sec = 8.0
transcription_model_name = "medium.en" 

###############################################
	
if __name__ == "__main__":
	in_wav = sys.argv[1]
	in_csv = sys.argv[2]
	out_md = sys.argv[3]

	print("Loading speech model...")
	model = WhisperModel(transcription_model_name, compute_type="float32")

	print("Loading BLS public key...")
	with open(bls_pubkey_file, "rb") as f: bls_pubkey_bytes = f.read()
	
	print(f"Loading frames from {in_csv}...")
	# Load payloads (l_payloads is a list of SignaturePayload)
	_res = payload.SignaturePayload.load_csv(in_csv)
	l_payloads: list[payload.SignaturePayload] = _res[0]
	l_payload_start_sam = _res[1]

	print(f"Getting transcription chunks from {in_wav}...")
	l_chunks, wav_fs_Hz = verification.wav_to_transcript_chunks(in_wav, model, window_sec, overlap_sec)
	n_chunks = len(l_chunks)
	start_sec = 0.0
	annotated_md = ""
	for ichunk in range(n_chunks):
		chunk = l_chunks[ichunk]
		end_sec = start_sec + chunk.info.duration

		# Collect this chunk's text and convert it to a list of tokens
		chunk_text = ""
		for seg in list(chunk.seg_iter): chunk_text += seg.text
		l_tokens = speech.regularize_transcript(chunk_text)
		
		# Compare our payloads to this list of tokens
		l_tswords = [tok.text for tok in l_tokens]
		l_match_idx = [] # i-th entry is the index of the i-th payload's first appearance in the chunk
		for pl in l_payloads: 
			ii = pl.find_in_token_list(l_tokens, bls_pubkey_bytes)
			l_match_idx.append(ii)

		# Create markdown for this chunk
		chunk_md = verification.annotate_chunk(chunk_text, l_tokens, l_payloads, l_match_idx, l_payload_start_sam, wav_fs_Hz)
		chunk_md = f"# Chunk {ichunk+1} of {n_chunks}; ({start_sec:.2f}-{end_sec:.2f} s)\n\n" + chunk_md + "\n"
		print(chunk_md)
		annotated_md += chunk_md 
		start_sec += chunk.info.duration

	print(f"Writing {out_md}")
	with open(out_md, "w", encoding="utf-8") as f:
	    f.write(annotated_md)
