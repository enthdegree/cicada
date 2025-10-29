# pip install faster-whisper numpy sounddevice
import os, numpy as np, sounddevice as sd
from faster_whisper import WhisperModel

SR = 16000
CHUNK = 30.0             # target chunk length, seconds
OVERLAP = 2.0            # carry 2 s into next chunk
MODEL = "medium.en"

model = WhisperModel(MODEL, device="cpu", compute_type="int8_float16")

def record_seconds(sec):
    n = int(SR*sec)
    audio = sd.rec(n, samplerate=SR, channels=1, dtype="float32")
    sd.wait()
    return audio[:,0].copy()

confirmed_text = []
last_end = 0.0           # seconds in the *global* timeline
carry = np.zeros(0, dtype=np.float32)

print("Listening… Ctrl+C to stop")
t0 = 0.0
while True:
    # collect ~30 s new audio, prepend 2 s overlap from previous chunk
    new_audio = record_seconds(CHUNK)
    audio = np.concatenate([carry, new_audio])
    # keep OVERLAP seconds from the tail to prepend next time
    keep = int(SR*OVERLAP)
    carry = audio[-keep:].copy()

    # decode current chunk; ask Whisper to use prior text for stability
    init_prompt = "".join(confirmed_text)[-300:] if confirmed_text else None
    segments, _ = model.transcribe(
        audio,
        language="en",
        condition_on_previous_text=bool(init_prompt),
        initial_prompt=init_prompt,
        beam_size=5,
        temperature=[0.0, 0.2, 0.4],
        vad_filter=False
    )

    # segments' times are chunk-relative; map to global using the chunk start
    # current chunk starts at global time t0 - OVERLAP
    chunk_start = t0 - OVERLAP
    stitched = []
    for s in segments:
        seg_start = chunk_start + s.start
        seg_end = chunk_start + s.end
        # drop anything that ends at or before last_end (duplicate from overlap)
        if seg_end <= last_end:
            continue
        # keep; optionally trim leading part if seg_start < last_end
        stitched.append(s.text)
        last_end = max(last_end, seg_end)

    if stitched:
        out = " ".join(t.strip() for t in stitched).strip()
        if out:
            confirmed_text.append(out)
            print(out)  # emit only the newly confirmed tail

    t0 += CHUNK  # advance global clock by the new non-overlapped audio
