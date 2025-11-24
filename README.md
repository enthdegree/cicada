# cicada

<p align="center">
  <img src="header_image.jpg" alt="malaise" width="50%">
</p>

Let's acoustically imprint speech in real-time with evidence it is not falsified. Evidence it is not edited or AI generated, for example.

We (the signers) will transcribe the last window of speech we hear into English, digitally sign the transcript, then transmit the digital signature acoustically. 
Now any sufficiently high-fidelity audio recording contains within it our attestation of the words we heard moments ago.

People who such a recording can extract our signatures from it and validate that they indeed match what is being said. 
Our attestations are evidence those recordings are not falsified.[1]

We stress two features:

 - It is the signer that needs to be trusted, not whoever is speaking
 - Real-world acoustics are signed, not any individual's recording 

Implementation details in [`DESIGN_NOTES.md`](./DESIGN_NOTES.md). Issues and application criticism are in [`ISSUES.md`](./ISSUES.md).

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

# Make a private key
python3 ./make_bls_keys.py
```

## Usage 
`cicada.py` is an interface to Cicada's individual applets. 

- `cicada.py sign` In a loop, transcribe audio from your mic and transmit acoustic signatures, signed with your BLS private key, through the loudspeaker
- `cicada.py verify` Given `recording.wav` and a BLS public key, produce `transcript.md` which is a transcript of `recording.wav`, annotated with matching signatures it found therein. 
- `cicada.py extract` Pull digital data frames out of a recording for later verification/debugging.
- `make_bls_keys.py` Generates a BLS keypair

## Underpinnings

- `cicada/speech.py` Speech transcription routines
- `cicada/modem.py` Convert data bits to/from audio samples
- `cicada/payload/` Payload definitions
- `cicada/verification.py` Utilities to compare `SignaturePayloads` to transcript text
- `cicada/fsk/` Physical-layer acoustic waveform
	- `cicada/fsk/waveform.py` Python defining the audio waveform and its modulation
	- `cicada/fsk/demodulate.py` Python demodulator for recordings

---

[1]: That is, we trust BLS short signatures aren't broken, that the imprinter's private key is secure and that the imprinter's transcript is faithful.
