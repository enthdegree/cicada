import numpy as np
import wave
import matplotlib.pyplot as plt
from scipy.signal import stft
import plot

p = { # Waveform parameters
    "fs": 44100,  # Real sample rate (Hz)
    "n_frame_sep": 64,  # Number of samples between frames
    "n_spp_re": 96,  # Number of samples per pulse
    "n_spp": 32,  # Number of complex samples per pulse
    "n_bits_per_frame": 4,  # Number of bits per frame
}

v_re_win = np.hamming(1+p["n_spp_re"])[:-1]  # Window function for real pulse shape
def define_pulses(p=p): # Generate real pulse matrix and the pilot pulse
    m_pulses = np.zeros((p["n_spp"], p["n_spp_re"]), dtype=np.float32) # Rows = fft bin, cols = real samples for this pulse frequency location
    for idx in range(p["n_spp"]):
        v_pulse_f = np.zeros(2*p["n_spp"], dtype=np.complex64) # 2x oversampled complex pulse spectrum
        v_pulse_f[idx] = 1.0  
        v_pulse = np.real(v_re_win[:p["n_spp_re"]] * np.tile(np.fft.ifft(v_pulse_f), 4)[:p["n_spp_re"]])
        v_pulse = v_pulse / np.sqrt(np.sum(v_pulse**2))  # Normalize pulse energy
        m_pulses[idx, :] = v_pulse
    v_pilot = np.zeros(p["n_spp_re"], dtype=np.float32)
    for idx_carrier in range(p["n_bits_per_frame"]):
        v_pilot += m_pulses[v_carriers[idx_carrier], :]
    v_pilot = v_pilot / np.sqrt(np.sum(v_pilot**2))
    return m_pulses, v_pilot

v_carriers = np.array([13, 15, 17, 19])
m_pulses, v_pilot = define_pulses()  # Generate the pulse matrix

def modulate_bits(v_bits, v_carriers=v_carriers, m_pulses=m_pulses, v_pilot=v_pilot, p=p): # Modulate bits into real samples
    n_bits = len(v_bits)
    n_frames = n_bits // p["n_bits_per_frame"] # Number of frames
    n_sam_per_frame = p["n_spp_re"]*2 + p["n_frame_sep"]
    m_frames = np.zeros((n_frames, n_sam_per_frame), dtype=np.float32)  # Initialize complex signal array

    idx_bit = 0
    for idx_frame in range(0, n_frames): # Build frames
        print(f"Building frame {idx_frame+1}/{n_frames}")

        # Assemble data pulse
        v_data_pulse = np.zeros(p["n_spp_re"], dtype=np.float32)
        for idx_carrier in range(p["n_bits_per_frame"]):
            sc = 1.0 if v_bits[idx_bit] == 1 else -1.0
            v_data_pulse += sc * m_pulses[v_carriers[idx_carrier], :]
            idx_bit += 1
        v_data_pulse = v_data_pulse / np.sqrt(np.sum(v_data_pulse**2))

        # Assemble frame
        v_frame = np.zeros(n_sam_per_frame, dtype=np.float32)
        v_frame[0:p["n_spp_re"]] = v_pilot
        v_frame[p["n_spp_re"]:2*p["n_spp_re"]] = v_data_pulse

        m_frames[idx_frame, :] = v_frame
    return m_frames

def make_test_wf(): # Create a test waveform
    n_bits = 1024  # Number of bits in the payload
    v_bits = np.random.RandomState(0).randint(0, 2, n_bits) # Random bits for payload
    m_frames = modulate_bits(v_bits)
    v_sam = m_frames.flatten(order='C')  # Flatten the frames into a single vector
    v_sam = np.int16(v_sam / np.max(np.abs(v_sam)) * 32767)
    with wave.open("wf.wav", "w") as wav_file: # Dump wav
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(p["fs"])
        wav_file.writeframes(v_sam.tobytes())

    # Save binary data to a text file
    with open("wf_data.txt", "w") as f:
        for idx_bit in range(n_bits):
            f.write(f"{v_bits[idx_bit]}")

    # Plot the first pulses
    n_plotsym = 6
    plot.wf(v_sam, "wf_plot.png", fs=p["fs"], nsam=p["n_spp_re"] * n_plotsym)

    # Compute STFT
    f, t, Zxx = stft(v_sam, fs=p["fs"], nperseg=p["n_spp_re"] * 8, noverlap=p["n_spp_re"] // 2 - 1)

    # Plot STFT
    plt.figure(figsize=(50, 30))
    plt.pcolormesh(t, f, 20 * np.log10(np.abs(Zxx) + 1e-10), shading='gouraud')
    plt.title("STFT of Samples")
    plt.xlabel("Time [s]")
    plt.ylabel("Frequency [Hz]")
    plt.colorbar(label="Magnitude [dB]")
    plt.grid()
    plt.savefig("wf_stft.png")
    plt.close()

if __name__ == "__main__":
    make_test_wf()