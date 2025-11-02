# acoustic-signature

Let's acoustically imprint speech in real-time with evidence it is not falsified (evidence it is not edited or AI generated, for example).

The imprinter transcribes the last window of speech they hear, digitally signs the transcript, then transmits the signature acoustically. 
Now any sufficiently high-fidelity audio recording contains within it a digital signature of the imprinter's transcript.
Listeners can recover these signatures and validate that their recording's transcript matches the signatures. 
If we trust the imprinter's transcipts, then the validation provides some evidence the recordings aren't falsified.

We stress two key features:

 - It is the signer we need to trust, not whoever is speaking
 - It is acoustics in the real world that are signed, not any individual's recording data 

Implementation details in [`DESIGN_NOTES.md`](./DESIGN_NOTES.md).

Issues and application criticism are in [`ISSUES.md`](./ISSUES.md).

# Project components 

## Applications

- `apps/sign.py` In a loop, transcribe audio and transmit acoustic signatures, signed with your BLS private key
- `apps/extract_frames.py` Extract data frames from `recording.wav`, write them to `frames.csv`
- `apps/annotate.py` Given `frames.csv`, `recording.wav` and a BLS public key, produce `annotation.md` which is a transcript of `recording.wav`, annotated with matching signatures from `frames.csv`.

## Underpinnings

- `imprint/frame.py` Frame assembly routines and waveform mod/demod object construction
- `imprint/speech.py` Speech transcription routines
- `imprint/fsk/` Physical-layer acoustic waveform
	- `fsk/waveform.py` Python defining the audio waveform and its modulation
	- `fsk/demodulate.py` Python demodulator for recordings
- `imprint/tests/` Tests used for waveform development

