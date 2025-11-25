# cicada

<p align="center">
  <img src="cicada/header_image.jpg" alt="malaise" width="50%">
</p>

Let's acoustically imprint speech in real-time with evidence it is not falsified. Evidence it is not edited or AI generated, for example.

We (the signers) will transcribe the last window of speech we hear into English, digitally sign the transcript, then broadcast the signature as sound. 

Now any sufficiently high-fidelity audio recording contains within it our attestation of the words we heard moments ago, that is, evidence they are not falsified.[1]
Anyone who posesses such a recording and our BLS public key can extract our signatures from it and validate they match the recording.  

We stress two features:

 - It is the signer that needs to be trusted, not whoever is speaking
 - Real-world acoustics carry the signature, not any individual's recording 

Implementation details in [`DESIGN_NOTES.md`](./DESIGN_NOTES.md). 
**IMPORTANT Issues and criticism are in [`ISSUES.md`](./ISSUES.md).**

## Setup

``` bash
# Make a python venv and install the requirements
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Build BLST and Python bindings, move them to the project root 
git clone https://github.com/supranational/blst
cd blst/bindings/python
python3 run.me
mv blst.py _blst.*.so ../../..
cd ../../..

# Generate a BLS key pair
python3 ./make_bls_keys.py
```

## Usage 
`cicada.py` is the top-level interface to cicada's individual tools. 
By default cicada looks for your public and private keys at `./bls_privkey.bin` `./bls_pubkey.bin` (point it to the right location in `--bls-pubkey` `--bls-privkey`).
By default output files are put in `./out/`.
For any routine that involves extracting frames from recorded audio, try adding the `--demod-plot` flag.

- `cicada.py sign`: Continuously transcribe mic audio and playback signed payloads as sound.
	- Example (with this optional `--signer-transcript` flag it also produces a transcript):
	```bash
	./cicada.py sign --signer-transcript 
	```
- `cicada.py verify`: Verify payloads against a WAV or a transcript.
	- From WAV (and auto-extract frames... ):
	```bash
	./cicada.py verify recording.wav 
	```
	- From transcript text and an existing CSV of payloads:
	```bash
	./cicada.py verify transcript.md --frames-csv out/recording_frames.csv
	```
- `cicada.py extract`: Extract payloads from a WAV file and dump them to a CSV.
	- Example:
	```bash
	./cicada.py extract recording.wav
	```

## Underpinnings

- `cicada/speech.py` Speech transcription routines
- `cicada/fsk/` Physical-layer acoustic waveform
- `cicada/modem.py` Abstraction over `fsk/` to convert data bits to/from audio samples
	- Has some hardcoded features like an LDPC code and a bitmask (excess regularity in the data frames can degrade demod)
- `cicada/payload/` Digital audio payload definitions
- `cicada/verification.py` Utilities to compare cicada payloads to transcripts

---

[1]: That is, we trust BLS short signatures aren't broken, that the imprinter's private key is secure and that the imprinter's transcript is faithful.
