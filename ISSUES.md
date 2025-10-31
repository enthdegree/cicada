# Application challenges

- What if the data that gets signed does not provide good evidence of the speech? The data that currently gets signed, a normalized audio transcript, is essentially a perceptual hash: https://en.wikipedia.org/wiki/Perceptual_hashing . Machine transcription will always be reliable. Perceptual hashes are bad and that there will be problems with them forever: https://rentafounder.com/the-problem-with-perceptual-hashes/ . It would be slightly better, (but would demand ~4x the data) to fill our data frames with [codec2's 450 bps signed streaming audio](https://www.rowetel.com/wordpress/?p=6212).
- What if it sounds annoying?
- What if they talk too fast and words get dropped?
- What if an attacker/spoofer can find speech with similar sound signature?
- Robustness is always a challenge. Successful payload recovery is really sensitive to how things are being recorded and the environment (channel nastiness, impulse noise).


# Logic issues

- `fsk/demodulator.py` uses a boneheaded frame sync strategy and it will not find frames whose contents are highly regular (full of zeros, for example).
- Write rate-1/2 frame encode/decode
- Write a bls interface
