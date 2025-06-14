# bitscream design notes

## target application
Real-time physical-layer acoustic cryptographic fingerprint.
Seek to imprint speech in real-time with evidence that it is not AI-generated.

Broadcast a low-bitrate digital-communications audio waveform over a speech so that any sufficiently high-fidelity recording of that speech can recover a payload.
The payload: a cryptographic singature of a transcript of the last window of speech.

Dimensional details:

- speech recognition goes transcribing data into a text buffer
- after every 4 seconds calculate a payload:
  - 512 bit (64 byte) version:
    - 48-byte BLS short signature on the last 16 words or numbers, uppercase, stripped of formatting [A-Z0-9]
    - 16-byte salt:
      - 16*6 bits: first char of last 16 words
      - 32 bit unix timestamp
  - 416 bit (52 byte) version:
    - same as above but omit the 16*6 bit = 12 byte transcript part

Assuming 4 words spoken per second (that's pretty fast) we need to send more than 1 signature per 4 seconds, thus we demand >104-128 reliable bits second.
Using a rate-1/2 code that's >208-256 uncoded bits.
Practically we need headers and frame control so really we want even more.

### challenges

- what if it sounds annoying
- what if our speech recognition is bad/gets words wrong
- what if they talk too fast and words get dropped
- what if an attacker/spoofer can find speech with similar sound signature

## waveform: BFSK
Parameters:

- `P`, even, real samples per pulse
- `N`, number in `[1,P/4)`, repetition period
- `F`, number in `[0,P/2)`, complex frequency offset
  - the occupied band is `44.1e3*F/P - 44.1e3*(F+2*N)/P` (however that wraps into complex `P/2`-point DFT frequencies...)
  - For high-band signals we need `F,P,N` so that `F+2*N <= P/2`
- `M`, number where `gcd(M,2*N)=1`, sequence multiplier
  - increases frequency separation between adjacent pulses, improves the sound

Transmission:

- For each DFT index `f=0,...,P/2` design a real length-`P` pulse: a tone shaped by a Hamming window
- For bit `b` at timeslot `t=0,1,2,...` transmit a pulse at index `F+[ (N*b + M*t)%(2*N) ]`.

Design outcomes:

- Rate = `44100/P b/s`
- Bandwidth = `44100/P*2*N Hz`
  - Here we generously ignore the spectral widening from windowing the tones.
  - Notice holding bandwidth fixed, scaling `P` to `cP` scales the rate by `1/c` and dispersion tolerance by `c^2`.
- isi avoidance = `P*N/44100 ms`
  - i.e. the waveform will not reuse the same frequency twice for this period

### Parameter optimization
Rewrite our desiredata as linear constraints:

- At least 280 uncoded bits per second: 280*P < 44.1e3
- Max frequency is 20 kHz: 44.1e3*F + 2*44.1e3*N -20e3*P < 0
- Min frequency is 16 kHz: -44.1e3*F + 16e3*P < 0

i.e. `[280, 0, 0; -20e3, 2*44.1e3, 44.1e3; 16e3, 0, -44.1e3]*[P;N;F] < [44.1e3, 0, 0]`

We can pick some whole numbers near the optimum:

- `P = 160`, rate is 275 bps
- `N = 8`, isi avoidance is 29 ms
- `F = 57` occupied band is 15.7-20.1 kHz (4.4 kHz)
- `M = 11` idk 

## Design notes

### noise 
We want our signal to live in as narrow a band as possible up near 20 kHz to stay out of the way of speech.
Impulse noise is everywhere.

### reverberation / echos / dispersion / multipath
Our channels are extremely temporally dispersive to the point where there is not really hope of a simple way to correct it. 
Sending out a regular short pilot pulse, in the receiver's cross-correlation the expected comb of direct-path peaks is drowned by a sea of echos.
It seems typical that there be more reflected paths than you would really want to keep track of, let alone at bad SNR.
Scrolling through some spectral measurements on a public dataset (https://mcdermottlab.mit.edu/Reverb/SurveyData.html) it seems like the echos above 16 kHz mostly die off by 100 ms if you're lucky.

### coherence & frequency error
The top half of the band, where we need our signal to live, spans 2-4 cm wavelength.
Concievably the tx and rx can move around that distance within 50 ms (i.e. ~2 mph).
There's probably some tx/rx clock drift too. 
In this case then after 256 samples a tone's phase might get offset ~45 degrees.
If we were matched-filtering that tone then the integration would be degraded by 3 dB at the end of the frame.
Thus we should avoid coherently integrating over anything longer than 256 real samples / ~6 ms.

### waveforms
We could hop various modulations around in frequency to avoid multipath.
Classic modulation choices: 

- FSK
- OOK
  - more spectrally efficient but sensitive to impulse noise
- BPSK
  - more sophisticated and technically promising but demod will be very sensitive to many implementation details given our horrible channel.

### block coding
target a 90% transcript success rate

- for small coded ber p, have (1-p)^n ~ exp(-np) = exp(-512p) < 0.9
- thus need p < 2e-4 
- using a curve for golay (12,24) we need 7 dB or more SNR per coded binary symbol
- thus assuming awgn + flat channel the limit for our FSK waveform is -14 dB real sample SNR, good

## experimental outcomes so far

- non-hopped bpsk pulses: [1 pilot + 4 data pulses per frame]
  - garbage outcome, couldn't distinguish between pilot and data pulses, hadn't yet realized reverb was so bad
- ofdm-like pulse-pairs: [96 sam training pulse, 96 sam data pulse, 64 sam guard interval]
  - training is a sum of training carriers
  - data is the same, except the sign of the training carriers are flipped depending on data
  - idea: to demod, correlate against the training carriers the correlate against the data 
  - problem: again, reverb makes it very difficult to lock-in on the training pulse, guard interval is 10x too small 
  - miraculously somehow achieved 25% uncoded BER with this in a high SNR test case
- iPhone 15 pro lossless mic rx spectrogram:
  - projector speakers tx gets really attenuated above 18 kHz
  - keys center at 5 kHz but make impulse noise all the way up to 20 kHz
  - Plosives and tapping make wideband noise up to 20 kHz

### outer bounds
If the params we pick are anywhere close to an idealized channel capacity estimate there's basically no hope to succeed. 

- Unsubstantiated guess the channel will have -10 dB SNR per real sample 
- Unsubstantiated guess the accumulated channel and frequency errors will be encompassed by thinking about uncorrected Doppler up to 2 m/s (4.5 mph). At 343 m/s speed of sound in air this shifts dft bins no more than ~0.6%. 
- Due to attenuation at band edges and coherence limits it makes sense to consider the capacity after integrating pulses into some complex scalar instead applying the Shannon-Hartley theorem on the raw 22.05 kHz complex samples.
  - Imagine matched-filtering a received tone that lines up exactly with a DFT bin so that if there were no frequency error, the matched filter output would be 1. With frequency error the correlation will instead be `y = sinc(pi*x) = sin(pi*x)/(pi*x)` where `x` is the # of DFT bins of frequency error we have. 
  - Without frequency error correction, we might ask that our DFT bins to be wide enough that Doppler shift won't affect the correlation by more than `y`. Thus we want `(Doppler shift, Hz) < x*(fft bin width, Hz)`, rearranging, `fft length < x*fs/(Doppler shift, Hz)`, so `fft length < x/(343/341-1)`. 
  - At 64 real samples (32 complex) `x = 0.188` so we take `y = -0.25 dB` loss due to frequency incoherence. The absolute limit for reliable comms on our symbols asserting we integrate pulses of 64-real-sample symbols is `(44.1e3/64 symbol rate Hz)*log2(1+10^((-10 dB real sample SNR + 3 dB real samples per complex sample + 15 dB complex samples per symbol - 0.25 dB doppler loss)/10)) = 1928 bits/sec`.
  - At 196 real samples (98 complex) `x=0.539` so we take 2.69 dB loss due to frequency incoherence. The absolute limit here is `794 bits/sec`.

Aerial acoustic communication literature review suggests the limit calculation is extremely optimistic, with inaudible long-distance waveforms achieving ~20 bits/sec using very prominent features (frequency-shift keying, chirp spread spectrum) and sophisticated receivers.

The parameters we picked above are 8-10 dB beneath estimated capacity.
Hopefully enough of a gap to be safe given our extreme non-idealities and band-limits.
We hope to get saved by our signal usually being out of band from the main sounds.
