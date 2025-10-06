# audio-watermark

Real-time physical-layer acoustic cryptographic fingerprint.
Seek to imprint speech in real-time with evidence that it is not AI-generated.

Play low-bitrate digital-communications audio over a speech so that a sufficiently high-fidelity recording can recover some data payload.
The payload: a cryptographic singature of a transcript of the last window of speech.
If we can match the transcript to the signature, and if we trust the signer, then we have evidence the audio wasn't AI

# Application details

## User-side (transmit-side) 

- Speech recognition on your phone goes transcribing data into a text FIFO buffer
- After the buffer collects 16 words, ingest them and transmit a 512-bit (64 byte) frame:
  - 16-byte plaintext header:
    - 16*6 bits: first char of the 16 words or numbers (encoded as truncated ASCII; for char `c` encode the last 6 bits of `c-0b0100000`)
    - 32 bit unix timestamp
  - 48-byte BLS short signature on the 16 words or numbers, uppercase, stripped of formatting [A-Z0-9]

Assuming 4 words spoken per second (that's pretty fast) we need to send around 1 signature per 4 seconds, thus we demand 128 reliable physical-layer bits second.
Using a rate-1/2 code that's 256 code-bits.

## Listener-side (receive-side)
The listener receives a recording of speech that has user signature packets in it, knowing the signer's public key.
From this recording the listener recovers all the data packets and a transcription of the speech.
The listener checks segments of the transcript to see ifi they match the signatures in the data packet.

# Challenges

- what if it sounds annoying
- what if our speech recognition is bad/gets words wrong
- what if they talk too fast and words get dropped
- what if an attacker/spoofer can find speech with similar sound signature
- robustness is a challenge. Successful payload recovery is really sensitive to how things are being recorded and the environment (channel nastiness, impulse noise).

# Physical-layer waveform: hopped frequency-shift keying

## Parameters

- $M$, FSK order in bits
- $P$, even, real samples per pulse
- $N$, number in $[1,P/2^{M+1})$, repetition period
- $F$, number in $[0,P/2)$, complex frequency offset
- Length-$P$ pulse-shaping window
- $f$, frequency hopping map, range is indices in the occupied band
  - intended to increase frequency separation between adjacent pulses and improve the sound slightly

## Modulation

- For each DFT index $f=0,...,P/2$ design a real length-$P$ pulse as so: a tone shaped by the window
- For bit $d=1,\dots,2^M$ at timeslot $t=0,1,2,...$ transmit the pulse at index $f(d,t)$
- Send data in blocks of $\lceil 1024/M \rceil$ pulses.

## Design outcomes

- Approximate uncoded bit rate = $M f_s/P \ \mathrm{bits}/\mathrm{sec}$
- Occupied band = $f_s \cdot F/P$ to $f_s \cdot (F+2^M N)/P$ 
  - Bandwidth = $2^M f_s N/P \ \mathrm{Hz}$
  - Here we generously ignore the spectral widening from windowing the tones.
  - Notice holding bandwidth fixed, scaling $P$ to $cP$ scales the rate by $1/c$ and dispersion tolerance by $c^2$.
- isi avoidance = $PN/f_s \ \mathrm{ms}$
  - i.e. $f$ can be designed so that the waveform will not occupy any frequency twice during this period

## Choice of parameters for our application
Our desiredata form linear constraints and a quadratic objective:

- At least 280 uncoded bits per second: $280 P < f_s M $
- Max frequency is 20 kHz: $f_s F + 2^M f_s N - 20\times 10^3 P < 0$
- Min frequency is 19 kHz: $-f_s F + 19\times 10^3 P < 0$
- Maximum isi avoidace possible given these constraints: $\text{maximize } PN$

For various $M$ we can pick some whole numbers near the optimum, all 275 bps and occupying 19.0-20.1 kHz (1.1 kHz):

- $M=1, [P,N,F] = [160,2,69]$, isi avoidance is 7 ms
- $M=2, [P,N,F] = [320,2,138]$, isi avoidance is 14 ms
- $M=3, [P,N,F] = [640,2,276]$, isi avoidance is 29 ms

The bottom two are beyond the limits of the available frequency resolution we guessed below.
So we pick $M=1$.

# Channel design notes

## Noise 
We want our signal to live in as narrow a band as possible up near 20 kHz to stay out of the way of speech.
Impulse noise is everywhere. A clap lasts ~100 ms.

## Reverberation / echos / dispersion / multipath
Our channels are extremely temporally dispersive to the point where there is not really hope of simple correction.
It is typical there are more reflected paths than you would really want to keep track of, let alone at bad SNR.
Sending out a regular short pilot pulse, in the receiver's cross-correlation the comb of intended peaks is drowned by a sea of echos.
Scrolling through some spectral measurements on a public dataset (https://mcdermottlab.mit.edu/Reverb/SurveyData.html) it looks like reverberations above 16 kHz mostly die off by 100 ms if you're lucky.

## Coherence & frequency error
The top half of the band, where we need our signal to live, spans 2-4 cm wavelength.
Concievably the tx and rx can move around that distance within 50 ms (i.e. ~2 mph).
In this case then after 256 samples a tone's phase might get offset ~45 degrees.
If we were matched-filtering that tone then the integrated signal would be degraded by 3 dB at the end of the frame.
Thus we should really worry about coherently integrating much longer than 256 real samples / ~6 ms.

# Waveform design notes
We could hop various modulations around in frequency to avoid multipath.
Classic modulation choices: 

- FSK
- OOK
  - more spectrally efficient (that is, for the same rate and bandwidth as FSK we'd get 4x as much isi avoidance) but a lot more sensitive to impulse noise
- BPSK
  - more sophisticated and technically promising but demod will be very sensitive to many implementation details given our horrible channel.

The best bet right now seems to be FSK.

## Block coding
target a 90% transcript success rate

- for small coded ber p, have $(1-p)^n \sim \exp(-np) = \exp(-512p) < 0.9$
- thus need $p < \sim 2\times 10^{-4}$
- using a curve for golay (12,24) we need 7 dB or more SNR per coded binary symbol. Really we'll aim for an LDPC code.
- thus assuming awgn + flat channel the limit for our FSK waveform is -14 dB real sample SNR, good

## Experimental outcomes

- non-hopped bpsk pulses: `[1 pilot + 4 data pulses per frame]`
  - garbage outcome, couldn't distinguish between pilot and data pulses
- ofdm-like pulse-pairs: `[96 sam training pulse, 96 sam data pulse, 64 sam guard interval]`
  - training is a sum of training carriers
  - data is the same, except the sign of the training carriers are flipped depending on data
  - idea: to demod, correlate against the training carriers the correlate against the data 
  - problem: again, reverb makes it very difficult to lock-in on the training pulse, guard interval is 10x too small 
  - miraculously somehow achieved 25% uncoded BER with this in a high SNR test case
- iPhone 15 pro lossless mic rx spectrogram:
  - projector speakers tx gets really attenuated above 18 kHz
  - keys center at 5 kHz but make impulse noise all the way up to 20 kHz
  - Plosives and tapping make wideband noise up to 20 kHz
  - Uncoded FSK does OK here as long as the fairly directive iPhone mic is aimed well

## Outer bounds
If the params we pick are anywhere close to an idealized channel capacity estimate there's basically no hope to succeed. 

- Unsubstantiated guess the channel will have -10 dB SNR per real sample 
- Unsubstantiated guess the accumulated channel and frequency errors will be encompassed by thinking about uncorrected Doppler up to 2 m/s (4.5 mph). At 343 m/s speed of sound in air this shifts dft bins no more than ~0.6%. 
- We've decided on pulse processing so it makes more sense to approximate channel capacity after integrating pulses.
  - Imagine matched-filtering a received tone that lines up exactly with a DFT bin so that if there were no frequency error, the matched filter output would be 1. With frequency error the correlation will instead be $y = \mathrm{sinc}(\pi x)$ where $x$ is the # of DFT bins of frequency error we have. 
  - Without frequency error correction, we might ask that our DFT bins to be wide enough that Doppler shift won't affect the correlation by more than multiplicative factor $y$. Thus we want $(\text{Doppler shift, Hz}) < x \times (\text{dft bin width, Hz})$, rearranging, $(\text{dft length}) < x f_s/(\text{Doppler shift, Hz})$, so $(\text{dft length}) < x/(343/341-1)$. 
  - At 64 real samples (32 complex) $x = 0.188$ so we take 0.25 dB loss due to frequency incoherence. The absolute limit for reliable comms on our symbols asserting we integrate pulses of 64-real-sample symbols is:
  $$f_s/(64 \text{ symbol rate, Hz}) \log_2\left(1+10^{\frac{1}{10} \times -10 \ \mathrm{dB} \text{ real sample SNR} + 3 \ \mathrm{dB} \text{ real samples per complex sample} + 15 \ \mathrm{dB} \text{ complex samples per symbol} - 0.25 \ \mathrm{dB}\text{ doppler loss}}\right) = 1928 \ \mathrm{bits}/\mathrm{sec}.$$
  - At 196 real samples (98 complex) $x=0.539$ so we take 2.69 dB loss due to frequency incoherence. The absolute limit here is $794 \ \mathrm{bits}/\mathrm{sec}$.

The parameters we picked above are 8-10 dB beneath estimated capacity.
Hopefully enough of a gap to be safe given our extreme non-idealities and band-limits.

## Prior work 
This is not a unique idea... people are working on similar things for images. (todo: find reference to this)

It would be nice to use the [quiet modem](https://quiet.github.io/docs/org.quietmodem.Quiet/) instead of rolling our own waveform. 
It includes [profiles](https://github.com/quiet/quiet-js/blob/master/quiet-profiles.json) very similar to our target: `ultrasonic-fsk-robust` is 8-FSK around 19 kHz with rate-1/2 FEC. 
It's unclear what bit rate is achieved and would take effort to pull our design in (frequency hopping, different FEC, different frame format). 
Given how simple the waveform proposed here is, the simplest approach seems to me to be to build it standalone and merge it into the quiet modem later if there is interest.

Aerial acoustic communication literature review suggests inaudible long-distance waveforms achieve ~20 bits/sec using very prominent features (frequency-shift keying, chirp spread spectrum) and sophisticated waveform designs.
We aim for 10x this rate but may have better channel conditions: communication beyond ~10 m is an unlikely use case. 
