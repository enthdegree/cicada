# Application challenges

- The application is conceptually confusing. In an age where people want to fool you with AI, what the average person really wants is ability to detect deepfakes. It is maybe less interesting that good-faith people can physically attest something isn't deepfaked.
- What if the data that gets signed does not provide good evidence of the speech? The data that currently gets signed, a normalized audio transcript, is essentially a [perceptual hash](https://en.wikipedia.org/wiki/Perceptual_hashing) Machine transcription will always be unreliable. Perceptual hashes are bad and that there will be problems with them forever (for example [here](https://rentafounder.com/the-problem-with-perceptual-hashes/)). It would be slightly better, (but would demand ~4x the data) to fill our data frames with [codec2's 450 bps signed streaming audio](https://www.rowetel.com/wordpress/?p=6212).
- There are all kinds of possible attacks: an attacker might jam the signals, or something else nasty, like collect a large dictionary of trusted signatures and transmit a collage of them. What if the speaker talks too fast and words get dropped, or the speaker intentionally confounds systematic transcription?
- Robustness is always a challenge. Successful payload recovery is really sensitive to how things are being recorded and the environment (channel nastiness, impulse noise).

# Logic issues

- Frame extraction is naive right now: each frame is compared to the entire transcript
- `fsk/demodulator.py` uses a naive frame sync strategy. It will not find frames whose contents are highly regular (full of zeros, for example).
- Write rate-1/2 frame encode/decode
- Write a bls interface
