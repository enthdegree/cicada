# acoustic-signature

Let's acoustically imprint speech in real-time with evidence that it is not AI-generated.

We'll listen for a transcript of the last window of the speech, sign it, then transmit an acoustic data frames so that any sufficiently high-fidelity audio recording can recover and validate the signature: if we can match the transcript to the signature, and if we trust the signer, then we have some evidence the audio wasn't AI.

# Project components 

Underpinnings:

- `fsk/` Physical-layer acoustic waveform
	- `fsk/waveform.py` Python defining the audio waveform and its modulation
	- `fsk/demodulate.py` Python demodulator for recordings
	- `fsk/waveform.js` Javascript re-implementation of waveform.py with one difference: waveform.js creates pulses with peak value 0.95 and waveform.py creates pulses with unit sample average power.
- `ldpc/` LDPC code definition 
	- `ldpc.py` Python rate-1/2 LDPC modulator and demodulator
	- `ldpc.js` An equivalent LDPC modulator in Javascript
- `bls/` BLS API (todo)


# Todo

- waveform.js + demodulate.py unit test
- ldpc.js + ldpc.py unit test: ber curve
- bls.js + bls.py unit test
- sign.html
	- we have a text box being populated with iphone speech recognition 
	- main loop: 
		- every 4 seconds eat the last 16 words of the text box,
		- make_frame() pack those 16 words into a frame as described in design_notes.md
		- play the frame as audio
- verify.py (signed_recording.wav + transcript.txt ---> frames.csv, transcript_annotated.txt)
	- find all the frames in signed_recording.wav and write them to frames.csv
	- for each frame, use the header to match it to the transcript. 
		- for each match to this frame (if any), annotate the transcript with a reference to this frame 
		- note whether only the header matches
	- write transcript_annotated.txt
