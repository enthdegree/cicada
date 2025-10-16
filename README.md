# audio-watermark

Let's acoustically imprint speech in real-time with evidence that it is not AI-generated.

We'll listen for a transcript of the last window of the speech, sign it, then transmit an acoustic data frames so that any sufficiently high-fidelity audio recording can recover and validate the signature: if we can match the transcript to the signature, and if we trust the signer, then we have some evidence the audio wasn't AI.

# Todo

- fsk.js
- fsk.js + demodulate.py unit test
- ldpc.js + ldpc.py unit test: ber curve
- bls.js + bls.py unit test
- encoder webapp 
- python decoder (output.wav + transcript.txt ---> frames.csv, transcript_annotated.txt)
