# Concept-level issues

This is a very high-friction apparatus. 
In some aspects inextricably so, aside from it being a prototype. 
It is currently, among other things, annoying-sounding, unreliable, vulnerable to attacks, extremely limited in applicability (we can attest clear, machine-readable English speech in a quiet room), and it demands users know about asymmetric key cryptography. 

- The imprinter must somehow publish their identity using the 11 characters of plaintext in payload headers... otherwise payloads in the wild have no authorship
- The application is conceptually confusing. In an age where people want to fool you with AI, what the average person really wants is ability to detect deepfakes. It is maybe less interesting that good-faith people can physically attest something isn't deepfaked.
- What if the data that gets signed does not provide good evidence of the speech? The data that currently gets signed, a normalized audio transcript, is essentially a [perceptual hash](https://en.wikipedia.org/wiki/Perceptual_hashing) Machine transcription will always be unreliable. Perceptual hashes are bad and that there will be problems with them [forever.](https://rentafounder.com/the-problem-with-perceptual-hashes/) It may be slightly better, but would demand 4x the data rate, to transmit signed digital streaming audio, like [codec2's 450 bits-per-second voice encoder](https://www.rowetel.com/wordpress/?p=6212).
- There are trivial attacks: an attacker or person of lesser trust can easily jam or clog our waveform's band. 
- Transcription is pretty weak information to sign. What if the speaker talks too fast and words get dropped, or the speaker intentionally confounds systematic transcription?
- Robustness is always a challenge. Successful payload recovery is really sensitive to how things are being recorded and the environment (channel nastiness, impulse noise).

# Logic issues

- Frame extraction is naive right now: each frame is compared to the entire transcript
- `fsk/demodulator.py` frame sync is unreliable right now. The extremely rudimentary fsk design might be at fault. It will not find frames whose contents are highly regular (full of zeros, for example).
