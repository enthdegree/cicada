# acoustic-signature

Let's acoustically imprint speech in real-time with evidence that it is not AI-generated.

We'll listen for a transcript of the last window of the speech, sign it, then transmit an acoustic data frames so that any sufficiently high-fidelity audio recording can recover and validate the signature: if we can match the transcript to the signature, and if we trust the signer, then we have some evidence the audio wasn't AI.

Implementation details in [`DESIGN_NOTES.md`](./DESIGN_NOTES.md).

# Project components 

Underpinnings:

- `fsk/` Physical-layer acoustic waveform
	- `fsk/waveform.py` Python defining the audio waveform and its modulation
	- `fsk/demodulate.py` Python demodulator for recordings
- `bls/` BLS API (todo)


# Todo

- improve mod/demod reliability
- rate-1/2 frame encode/decode
- bls 
- verify_transcript.py (signed_recording.wav + transcript.txt ---> frames.csv, transcript_annotated.txt)
	- find all the frames in signed_recording.wav and write them to frames.csv
	- for each frame, use the header to match it to the transcript. 
		- for each match to this frame (if any), annotate the transcript with a reference to this frame 
		- note whether only the header matches
	- write transcript_annotated.txt
