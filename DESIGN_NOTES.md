# Prior work 

## Physical-layer watermarking
This is not a unique idea. 
It is a bit of a fad right now, I think.
As a starting reference, a team at Cornell is working on a similar appliance for images[1].
ROC camera[2] is some zero-knowledge-proof image sensor.

## Acoustic communication
It would have been nice to use Quiet[3] instead of rolling our own physical & transport layers (in `fsk/` and `modem.py`). 
Quiet includes profiles very similar to our target: `ultrasonic-fsk-robust` is 8-FSK around 19 kHz with rate-1/2 FEC. 
It's unclear what bit rate is achieved and would take effort to pull our design in (frequency hopping, FEC, frame format). 

Aerial acoustic communication surveys[4] suggest state-of-the-art inaudible long-distance waveforms achieve ~20 bits/sec using very prominent features (frequency-shift keying, chirp spread spectrum) and sophisticated waveform designs.
We aim for 10x this rate but may have better channel conditions: communication beyond ~10 m is an unlikely use case. 

# Application details 

## `cicada.py sign`: Signer (transmit-side) 

Speech recognition (some Whisper model[5]) goes transcribing a rolling window of text every few seconds (configurable, defaults to once per ~5s).
From each transcription a 512-bit (64 byte) SignaturePayload is formed, described below.
Each SignaturePayload is transmitted acoustically using the modulation scheme described below.

### SignaturePayload structure
A SignaturePayload (`cicada/payloads/signature.py`) is comprised of these data fields:

- 128-bit header
	- `bits  0-31`: 32 bit unix timestamp
	- `bits 32-39`: 8 bit int of # of words this SignaturePayload's signature represents
	- `bits 40-128`: 11 character ascii plaintext header message 
- 384-bit signature
	-  `bits 129-512`: 48 byte BLS short signature on a regularized list of transcript words

The SignaturePayload is block-coded using a (1026,513) binary LDPC code to form a frame of 1026 coded binary symbols.

## `cicada.py verify`: Verifier (receive-side)

Run a python script to annotate and verify some audio recording. 
From this recording the listener recovers a full speech transcript and a bundle of SignaturePayloads.
The listener matches the SignaturePayloads to the transcript to find matches.

## `fsk/` Acoustic data modulation

Data is modulated into acoustic waves using a very simple hopped-FSK-like waveform in terms of the following definitions

- $f_s=44100 \text{ Hz}$, tx sample rate
- $f_c \in (0,f_s/2)$, center frequency (Hz)
- $f_{\text{bw}} \in (0, 2f_c \wedge 2(f_s/2-f_c))$ bandwidth (Hz)
- $B\in \mathbb{N}$, bits per FSK symbol
- $f_{\text{sym}}$, symbol rate (Hz)
- $s$ sparsity factor; avoid reusing the same pulse for $s$ symbol periods
- $p$ is some number that controls the frequency hopping pattern

Form a bank of some $2^B s$ real pulses $P_k, \ k=0, \dots, 2^B s-1$: 
for $k=0,\dots, 2^B s-1$, then $P_k$ is a windowed tone of duration $1/f_{\text{sym}}$, the tone's frequency at $f_c+f_{\text{bw}}(\frac{k}{s 2^B} - \frac{1}{2}).$

For each frame, to transmit a symbol $b\in\{0,\dots,2^B-1}$ at time $t$, transmit pulse $P[b s + (p t\bmod{s})]$.

### Choice of FSK parameters

The application motivates choice of parameters:

- Number of samples per pulse, $n_{\text{spp}} = f_s/f_{\text{sym}}$ should be a whole number to make modulation easy. 
- To meet the data rate requirement for our application we need $Bf_{\text{sym}} \geq 256.$
- Symbols at each time period should be as distinguishable as possible. For some SNR $x$ say $w_x$ is the number of $n_{\text{spp}}$-point fft bins that contain all but some fraction $x$ of the pulse window function's energy.[6] Picking $f_{\text{bw}}{2^{B+1}}>w_x$ gives the waveform an SNR ceiling of $x$. 
- Parameters should be chosen to reduce inter-symbol interference (ISI). In practice this means pulses in the future should avoid parts of the band that were used recently. We can write the minimum separation in index between a pulse now and a pulse some $k$ time indices in the future as: $d_k=\min_t |(pt \bmod s) - (p(t+k) \bmod s)|.$ Those pulse's center frequencies are separated by no less than $b\_k = \frac{d\_k f\_{\text{bw}}}{s 2^B f\_{\text{sym}}}$ frequency bins. When $k,p<s$ then $d_k=\min(kp\bmod s, s-(kp\bmod s)).$ The first few of $b_1,b_2,b_3,\dots$ should be large long enough that ISI is avoided.[7] 
- Demodulator synchronization motivates choice of large $s$ and $p$ coprime from $s$.

$[B=1,f_{\text{sym}}=344.5,s=63,p=16,f_c=18.5\text{ kHz},f_{\text{bw}}=3\text{ kHz}]$ yields $n_{\text{spp}}=128$ and $b_k > 1$ for $k=1,2,3$.

### Channel comments

Channel and implementation difficulties motivate use of hopped FSK. 
To stay out of the way of human speech, the waveform should occupy as narrow a band as possible near 20 kHz.

Scrolling through some spectral measurements on a public dataset[8] it looks like reverberations above 16 kHz mostly die off by 100 ms if you're lucky.
Sending out a regular short pilot pulse, the comb of intended peaks for the direct path in the receiver's cross-correlation is drowned by a sea of echos.
It is typical there are more reflected paths than one really wants to keep track of, let alone at low SNR. 
Our channels are extremely temporally dispersive to the point where it is difficult to imagine any simple waveform that takes advantage of phase features, pushing us towards FSK.
Hopping helps the signal avoid reverberation.


# Notes and references 

- [1]: Peter Michael et. al. 2025 "Noise-Coded Illumination for Forensic and Photometric Video Analysis" https://dl.acm.org/doi/10.1145/3742892
- [2]: ROC camera: https://roc.camera/
- [3]: Quiet modem here: https://quiet.github.io/docs/org.quietmodem.Quiet/ ; Quiet reliable profiles here: https://github.com/quiet/quiet-js/blob/master/quiet-profiles.json
- [4]: Lee et. al. "Chirp signal-based aerial acoustic communication for smart devices" here: https://ieeexplore.ieee.org/abstract/document/7218629
- [5]: Whisper by OpenAI: https://github.com/openai/whisper . Actually a slightly regularized version of a Whisper transcript, see `speech.py`
- [6]: For a periodic Hann window, $w_{-10\text{ dB}}= \sim 1.9, \ w_{-20 \text{ dB}}=\sim 2.45$
- [7]: Borrowing $w_x$ from the previous point, consider designing for a high-SNR high-ISI case where $4$ past pulses present in current samples with at least $3$ dB attenuation. Picking parameters that yield $b_k > w_{-16 \text{ dB}},\ k=1,2,3,4$, then the SNR will drop to no worse than 10 dB due to ISI.
- [8]: Traer and McDermott 2016, "Statistics of natural reverberation enable perceptual separation of sound and space" here: https://mcdermottlab.mit.edu/Reverb/SurveyData.html 

