# acoustic-signature

Let's acoustically imprint speech in real-time with evidence that it is not AI-generated.

We'll listen for a transcript of the last window of the speech, sign it, then transmit an acoustic data frames so that any sufficiently high-fidelity audio recording can recover and validate the signature: if we can match the transcript to the signature, and if we trust the signer, then we have some evidence the audio wasn't AI.

Implementation details in [`DESIGN_NOTES.md`](./DESIGN_NOTES.md).

# Project components 

## Applications

- `sign.py` In a loop, transcribe audio and transmit acoustic signatures, signed with your BLS private key
- `transcribe.py` Form a `transcription.txt` from `recording.wav` 
- `verify.py` Given `transcription.txt`, `recording.wav` and a BLS public key, produce `transcription_annotated.md` which is annotated with signed portions of the transcription.

## Underpinnings

- `frame.py` Frame assembly routines and waveform constructor
- `speech.py` Speech transcription routines
- `fsk/` Physical-layer acoustic waveform
	- `fsk/waveform.py` Python defining the audio waveform and its modulation
	- `fsk/demodulate.py` Python demodulator for recordings
- `tests/` Tests used for waveform development

