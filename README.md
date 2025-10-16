# audio-watermark

Real-time physical-layer acoustic cryptographic fingerprint.
Seek to imprint speech in real-time with evidence that it is not AI-generated.

Play low-bitrate digital-communications audio over a speech so that a sufficiently high-fidelity recording can recover some data payload.
The payload: a cryptographic singature of a transcript of the last window of speech.
If we can match the transcript to the signature, and if we trust the signer, then we have evidence the audio wasn't AI
