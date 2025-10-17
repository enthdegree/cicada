# Application details 

## User-side (transmit-side) details 

A browser webapp will play audio signatures through a loudspeaker. 
One runs this on, say, a cell phone browser to sign audio in near-realtime.

- Speech recognition on your phone goes transcribing data into a text FIFO buffer
- After the buffer collects 16 words, ingest them and transmit a 512-bit (64 byte) payload:
	- 128-bit plaintext header:
		- 16*6 bits: first char of the 16 words or numbers (encoded as truncated ASCII; for char `c` encode the last 6 bits of `c-0b0100000`)
		- 32 bit unix timestamp
	- 384-bit BLS short signature on the 16 words or numbers, uppercase, stripped of formatting [A-Z0-9]

The 512-bit payload will be coded to a rate-1/2 LDPC codeword to a frame of 1024 coded bits.
Assuming 4 words spoken per second (that's pretty fast) a frame is produced once per 4 seconds. 
So we demand a reliable data rate of 128 bits (256 coded bits) per second.

The current approach is to playback hopped FSK pulses, described below.

## Listener-side (receive-side) details

Verification is run through a python script.
We get a recording of some speech that had payloads in it.
The verifier knows and trusts the signer's public key.
From this recording the listener recovers a transcript of the speech, and all the payloads.
The listener checks segments of the transcript to see if they match the payloads.

## Challenges

- what if it sounds annoying
- what if our speech recognition is bad/gets words wrong
- what if they talk too fast and words get dropped
- what if an attacker/spoofer can find speech with similar sound signature
- robustness is a challenge. Successful payload recovery is really sensitive to how things are being recorded and the environment (channel nastiness, impulse noise).

# Channel

Channel and implementation difficulties motivate use of hopped FSK. 

Scrolling through some spectral measurements on a public dataset[1] it looks like reverberations above 16 kHz mostly die off by 100 ms if you're lucky.
Sending out a regular short pilot pulse, the comb of intended peaks for the direct path in the receiver's cross-correlation is drowned by a sea of echos.
It is typical there are more reflected paths than one really wants to keep track of, let alone at low SNR. 
Our channels are extremely temporally dispersive to the point where it is difficult to imagine any simple waveform that takes advantage of phase features, pushing us towards FSK.
Hopping helps the signal avoid reverberation.

To stay out of the way of human speech, the waveform should occupy as narrow a band as possible near 20 kHz.

## Coherence & frequency error
The top half of the band, where we need our signal to live, spans 2-4 cm wavelength.
Concievably the tx and rx can move around that distance within 50 ms (i.e. ~2 mph).
In this case then after 256 samples @ 44.1 kHz a tone's phase might get offset ~45 degrees.
If we were matched-filtering that tone then the integrated signal would be degraded by 3 dB at the end of the frame.
Thus we should really worry about coherently integrating pulses much longer than 256 real samples / ~6 ms.

## Block coding
Let's target a 90% frame recovery success rate.
For small data ber $p$, we'll have $(1-p)^n \sim \exp(-np) = \exp(-512p) < 0.9$
Thus we'll need $p < \sim 2\times 10^{-4}$.
Using a curve for Golay (12,24) we are this reliable above 7 dB SNR per codeword bit, which isn't crazy. 

# Hopped FSK waveform

- $f_s=44100 \text{ Hz}$, tx sample rate
- $f_c \in (0,f_s/2)$, center frequency (Hz)
- $f_{\text{bw}} \in (0, 2f_c \wedge 2(f_s/2-f_c))$ bandwidth (Hz)
- $B\in \mathbb{N}$, bits per FSK symbol
- $f_{\text{sym}}$, symbol rate (Hz)
- $s$ sparsity factor; avoid reusing the same pulse for $s$ symbol periods
- $p$ is some number that controls the frequency hopping pattern

Form a bank of some $2^B s$ real pulses: 
for $k=0,\dots, 2^B s-1$, then $P[k]$ is a windowed tone of duration $1/f_{\text{sym}}$ with spectral peak at $f_c+f_{\text{bw}}(\frac{k}{s 2^B} - \frac{1}{2}).$

For each frame, to transmit a symbol $b\in\{0,\dots,2^B-1}$ at time $t$, transmit pulse $P[b s + (p t\bmod{s})]$.

## Choice of parameters

The application motivates choice of parameters:

- Number of samples per pulse, $n_{\text{spp}} = f_s/f_{\text{sym}}$ should be a whole number to make modulation easy. 
- To meet the data rate requirement for our application we need $Bf_{\text{sym}} \geq 256.$
- Symbols at each time period should be as distinguishable as possible. For some SNR $x$ say $w_x$ is the number of $n_{\text{spp}}$-point fft bins that contain all but some fraction $x$ of the pulse window function's energy.[2] Picking $f_{\text{bw}}{2^{B+1}}>w_x$ gives the waveform an SNR ceiling of $x$. 
- Pulse parameters should be chosen to reduce inter-symbol interference (ISI). We can write the minimum separation in index between a pulse now and a pulse some $k$ time indices in the future as: $d_k=\min_t |(pt \bmod s) - (p(t+k) \bmod s)|.$ Those pulse's center frequencies are separated by no less than $b\_k = \frac{d\_k f\_{\text{bw}}}{s 2^B f\_{\text{sym}}}$ frequency bins. When $k,p<s$ then $d_k=\min(kp\bmod s, s-(kp\bmod s)).$ One should ensure that each $b_k,\ k=1,\dots K$ is large enough that ISI is avoided.[3] 
- Demodulator synchronization motivates choice of large $s$ and $p$ coprime from $s$.

$[B=1,f_{\text{sym}}=344.5,s=63,p=16,f_c=18.5\text{ kHz},f_{\text{bw}}=3\text{ kHz}]$ yields $n_{\text{spp}}=128$ and $b_k > 1$ for $k=1,2,3$.

# Prior work 

## Physical-layer watermarking
This is not a unique idea. As a starting reference, a team at Cornell is working on a similar appliance for images[4].

## Acoustic communication
It would have been nice to use Quiet[5] instead of rolling our own FSK mod + LDPC coding. 
Quiet includes profiles ) very similar to our target: `ultrasonic-fsk-robust` is 8-FSK around 19 kHz with rate-1/2 FEC. 
It's unclear what bit rate is achieved and would take effort to pull our design in (frequency hopping, FEC, frame format). 

Aerial acoustic communication surveys[6] suggest state-of-the-art inaudible long-distance waveforms achieve ~20 bits/sec using very prominent features (frequency-shift keying, chirp spread spectrum) and sophisticated waveform designs.
We aim for 10x this rate but may have better channel conditions: communication beyond ~10 m is an unlikely use case. 

# Notes and references 

- [1]: Traer and McDermott 2016, "Statistics of natural reverberation enable perceptual separation of sound and space" here: https://mcdermottlab.mit.edu/Reverb/SurveyData.html 
- [2]: For a periodic Hann window, $w_{-10\text{ dB}}= \sim 1.9, \ w_{-20 \text{ dB}}=\sim 2.45$
- [3]: Borrowing $w_x$ from the previous point, consider designing for a high-SNR high-ISI case where $4$ past pulses present in current samples with at least $3$ dB attenuation. Picking parameters that yield $b_k > w_{-16 \text{ dB}},\ k=1,2,3,4$, then the SNR will drop to no worse than 10 dB due to ISI.
- [4]: Peter Michael et. al. 2025 "Noise-Coded Illumination for Forensic and Photometric Video Analysis" https://dl.acm.org/doi/10.1145/3742892
- [5]: Quiet modem here: https://quiet.github.io/docs/org.quietmodem.Quiet/ ; Quiet reliable profiles here: https://github.com/quiet/quiet-js/blob/master/quiet-profiles.json
- [6]: Lee et. al. "Chirp signal-based aerial acoustic communication for smart devices" here: https://ieeexplore.ieee.org/abstract/document/7218629
