import numpy as np
import scipy as sp
import wave
import matplotlib.pyplot as plt

params = { # Waveform parameters
    "fs": 44100,  # Real sample rate (Hz)
    "n_pulse_len_re": 160, # P; length of pulse in real samples
    "n_hop_sequence_len": 8,  # N; Length of the hopping sequence; after this many hops the hopped BFSK repeats
    "n_freq_offset": 57, # Frequency bin offset (index of a P/2-point complex DFT)
}
v_win_idx = 2*(np.pi*(np.arange(params["n_pulse_len_re"]) - params["n_pulse_len_re"]/2))/params["n_pulse_len_re"]
v_pulse_win = np.sin(v_win_idx)/v_win_idx
v_pulse_win[params["n_pulse_len_re"]//2] = 1
v_pulse_win_fft_magnitude = np.abs(np.fft.fft(v_pulse_win))

def define_pulses(p=params): # Generate real pulse matrix
    n_fft_bins = p["n_pulse_len_re"] // 2
    m_pulses = np.zeros((n_fft_bins, p["n_pulse_len_re"]), dtype=np.float32) # Rows = fft bin, cols = real samples for this pulse frequency location
    for idx in range(n_fft_bins):
        v_pulse_f = np.zeros(2*n_fft_bins, dtype=np.complex64) # 2x oversampled complex pulse spectrum
        v_pulse_f[idx] = 1.0  
        v_pulse = np.real(v_pulse_win * np.fft.ifft(v_pulse_f))
        v_pulse = v_pulse / np.sqrt(np.sum(v_pulse**2))  # Normalize pulse energy
        m_pulses[idx, :] = v_pulse
    return m_pulses

v_perm = np.arange(params["n_hop_sequence_len"])*3 % params["n_hop_sequence_len"]
v_carriers = params["n_freq_offset"] + np.concatenate((v_perm, params["n_hop_sequence_len"]+v_perm))  # Repeat permutation for two sequences
m_carriers = v_carriers.reshape(2, -1)  # Reshape into two rows for BFSK hopping
m_pulses = define_pulses()  # Generate the pulse matrix

def modulate_bits(v_bits, m_carriers=m_carriers, m_pulses=m_pulses, p=params): # Modulate bits into real samples
    m_hops = np.array([
        m_pulses[m_carriers[v_bits[idx_bit], idx_bit % params["n_hop_sequence_len"]], :] 
        for idx_bit in range(len(v_bits))
    ], dtype=np.float32)
    return m_hops

def make_test_wf(m_carriers=m_carriers, m_pulses=m_pulses, p=params): # Create a test waveform
    n_bits = 1024  # Number of bits in the payload
    v_bits = np.random.RandomState(0).randint(0, 2, n_bits) # Random bits for payload
    m_hops = modulate_bits(v_bits)
    v_sam = m_hops.flatten(order='C')  # Flatten the frames into a single vector
    v_sam = np.int16(v_sam / np.max(np.abs(v_sam)) * 32767)
    v_sam = np.pad(v_sam, (params["fs"], params["fs"]), mode='constant', constant_values=0)
    with wave.open("wf.wav", "w") as wav_file: # Dump wav
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(params["fs"])
        wav_file.writeframes(v_sam.tobytes())

    # Save binary data to a text file
    with open("wf_data.txt", "w") as f:
        for idx_bit in range(n_bits):
            f.write(f"{v_bits[idx_bit]}")

    # Plot v_pulse_win
    plt.figure(figsize=(10, 6))
    plt.scatter(np.fft.fftfreq(params["n_pulse_len_re"]), 40 * np.log10(v_pulse_win_fft_magnitude))
    plt.title("Frequency response of Pulse Window applied twice (dB)")
    plt.xlabel("Frequency Bin")
    plt.ylabel("Magnitude [dB]")
    plt.grid()
    plt.ylim(-40,120)
    plt.savefig("v_pulse_win_fft.png")
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(np.arange(len(v_pulse_win)) / params["fs"], v_pulse_win)
    plt.title("Pulse Window Function")
    plt.xlabel("Time [s]")
    plt.ylabel("Amplitude")
    plt.grid()
    plt.savefig("v_pulse_win.png")
    plt.close()


    # Plot the first 6 pulses
    plt.figure(figsize=(10, 6))
    n_samples = 6 * params["n_pulse_len_re"]  # Show first 6 pulses
    plt.plot(np.arange(n_samples) / params["fs"], v_sam[:n_samples])
    plt.title("First 6 Pulses")
    plt.xlabel("Time [s]")
    plt.ylabel("Amplitude")
    plt.grid()
    plt.savefig("wf_pulses.png")
    plt.close()

    # Plot STFT of first 24 sample periods
    n_samples = 24 * params["n_pulse_len_re"]

    # Compute STFT
    n_fft = params["n_pulse_len_re"]
    n_overlap = n_fft // 4 
    f, t, Zxx = sp.signal.stft(v_sam[:n_samples], 
                        fs=params["fs"],
                        nperseg=n_fft,
                        noverlap=n_overlap,
                        window='blackman')

    # Plot STFT
    plt.figure(figsize=(24, 8))
    plt.pcolormesh(t, f, np.abs(Zxx), shading='gouraud')
    plt.title('STFT of First 24 Sample Periods')
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [s]')
    plt.colorbar(label='Magnitude')
    plt.grid(True)
    plt.savefig('wf_stft.png')
    plt.close()

    
if __name__ == "__main__":
    make_test_wf()