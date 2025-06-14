import numpy as np
import scipy as sp
import wave
import matplotlib.pyplot as plt

params = { # Waveform parameters
    "fs": 44100,  # Real sample rate (Hz)
    "n_pulse_len_re": 160, # P; length of pulse in real samples
    "n_repetition_period": 8,  # N; Number of pulses before repeating the frequency hopping sequence
    "n_freq_offset": 57, # Frequency bin offset (index of a P/2-point complex DFT)
    "n_seq_jump": 5, # Multiplier for frequency hopping sequence
}

v_pulse_win = np.hamming(1+params["n_pulse_len_re"])[:-1]  # Window function for real pulse shape
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

n_hop_bins = 2*params["n_repetition_period"]
v_carriers = ((np.arange(n_hop_bins) * params["n_seq_jump"]) % n_hop_bins) + params["n_freq_offset"]
m_carriers = v_carriers.reshape(2, -1) # Carrier frequency indices for each bit
m_pulses = define_pulses()  # Generate the pulse matrix

def modulate_bits(v_bits, m_carriers=m_carriers, m_pulses=m_pulses, p=params): # Modulate bits into real samples
    m_hops = np.array([
        m_pulses[m_carriers[v_bits[idx_bit], idx_bit % params["n_repetition_period"]], :] 
        for idx_bit in range(len(v_bits))
    ], dtype=np.float32)
    return m_hops

def make_test_wf(m_carriers=m_carriers, m_pulses=m_pulses, p=params): # Create a test waveform
    n_bits = 1024  # Number of bits in the payload
    v_bits = np.random.RandomState(0).randint(0, 2, n_bits) # Random bits for payload
    m_hops = modulate_bits(v_bits)
    v_sam = m_hops.flatten(order='C')  # Flatten the frames into a single vector
    v_sam = np.int16(v_sam / np.max(np.abs(v_sam)) * 32767)
    with wave.open("wf.wav", "w") as wav_file: # Dump wav
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(params["fs"])
        wav_file.writeframes(v_sam.tobytes())

    # Save binary data to a text file
    with open("wf_data.txt", "w") as f:
        for idx_bit in range(n_bits):
            f.write(f"{v_bits[idx_bit]}")

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
    n_fft = 160
    n_overlap = n_fft // 4
    f, t, Zxx = sp.signal.stft(v_sam[:n_samples], 
                        fs=params["fs"],
                        nperseg=n_fft,
                        noverlap=n_overlap,
                        window='hamming')

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