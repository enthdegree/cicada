# Concept-level issues

This is a very high-friction apparatus for a fantasy-world application. 
It is currently, among other things:

- annoying-sounding
- unreliable
- vulnerable to attacks
- extremely limited in applicability (we can attest clear, machine-transcribable English speech spoken with regular cadence in a quiet room)
- demands users know about asymmetric key cryptography. 

Furthermore,

- The application is conceptually confusing. In an age where people want to fool you with AI, what the average person really wants is ability to detect deepfakes. It is maybe less interesting that good-faith people can physically rig a speech to attest it *isn't* deepfaked.
- The imprinter must somehow publish their identity using the 11 characters of plaintext in payload headers... otherwise we do not know the authorship of payloads in the wild
- Transcription is pretty weak information to sign. What if the speaker talks too fast and words get dropped, or the speaker intentionally confounds systematic transcription? Machine transcription will always be unreliable. The data that currently gets signed, a normalized audio transcript, is essentially a [perceptual hash.](https://en.wikipedia.org/wiki/Perceptual_hashing). Perceptual hashes are bad and there will be problems with them [forever.](https://rentafounder.com/the-problem-with-perceptual-hashes/) It may be slightly better, but would demand 4-5x the data rate (thus a lot more sophistication), to send signed, digital streaming audio like [codec2's 450 bits-per-second voice encoder](https://www.rowetel.com/wordpress/?p=6212).
- There are trivial attacks: an attacker or person of lesser trust can easily jam or clog our waveform's band. 
- Robustness is a challenge. Successful payload recovery is really sensitive to how things are being recorded and the environment (channel nastiness, impulse noise). 

# Implementation issues

- `modem.py` is serving a ton of different purposes right now, lots of hardcoding happens there, like the LDPC FEC construction. If we were being serious then transport layer logic would be split out of modem and we would use a real FEC library instead of this pyldpc nonsense.
- Our brain-dead signalling demands really low rate and high SNR to have any hope of working. The waveform does not survive default iPhone voice memo compression, for example. Many of its features are based on superstition rather than evidence... does the hopping really improve reliability in resonant spaces? Is the LDPC coding actually providing any improvement?
- Many frames are dropped. Demodulation could clearly be doing better: frame and even pulse boundaries are often cleanly apparent in `pulse_energy.png` (run `--demod-plot` during extract). Frame sync, demod, basically everything important about the physical layer /currently seems hamstrung by very heuristic/hacky normalization in `demodulator.py`'s `pulse_energy_map` routine. 
- Frame sync during demodulation without a header fails when the payload data is extremely regular. To avoid this case in practice we use a random bit mask in `modem.py`.
- The Whisper speech model sometimes hangs trying to get transcripts out of particularly difficult recordings. This is maybe just a configuration mistake. 
- `extract` is untested for `PlaintextPayload`s. This path is important for experimentation towards improving demod. 
- `extract` is very memory-inefficient: it loads and demodulates a recording's entire sample vector all at once, creating a massive pulse energy map. Demodulation should *really* be windowed instead.
- `SignaturePayload` matching (`payload/signature.py`) is naive right now: each payload is compared to the entire transcript. Timestamps are recovered but aren't verified to be sane. This creates a lot of false-positives for signatures with only a few words in them. For example, if someone says "I don't know." in silence a lot, all the payloads for that text will match, differentiated only by timestamp. 