""" 
Decode rx.wav 
"""
import numpy as np
import scipy as sp
import wave
import matplotlib.pyplot as plt
import wf

fname_wf = "rx.wav"
n_oversample = 4
missing_data_carrier_penalty = 1e3
n_spp_os = wf.p["n_spp_re"] * n_oversample
n_frame_sep_os = wf.p["n_frame_sep"] * n_oversample
n_winlen = int(2*n_spp_os + n_frame_sep_os)
n_winshift = n_spp_os

# Frame search parameters
aafilt = sp.signal.firwin(1024, 0.45)
def re2cx(v_re, aafilt=aafilt):  # shift, low-pass filter, decimate
    v = v_re * np.exp(-1j * np.pi/2 * np.arange(len(v_re)))
    v_filtered = sp.signal.convolve(v, aafilt, mode='full')
    trim_start = (len(v_filtered) - len(v)) // 2
    v_filtered = v_filtered[trim_start:trim_start + len(v)]
    return v_filtered[::2]

# read rx
wave_rx = wave.open(fname_wf, "r")
buf_rx = wave_rx.readframes(wave_rx.getnframes())
v_rx = np.frombuffer(buf_rx, dtype=np.int16).astype(np.float64) 
wave_rx.close()

# oversample the waveforms
v_rx_os = sp.signal.resample(v_rx, len(v_rx) * n_oversample)
v_pilot_os = sp.signal.resample(wf.v_pilot, len(wf.v_pilot) * n_oversample)
m_pulses_os = np.array([sp.signal.resample(pulse, len(pulse) * n_oversample) for pulse in wf.m_pulses])

# Coherent correlation with pilot pulses
v_pilot_corr = sp.signal.correlate(v_rx_os, v_pilot_os, mode='same', method='fft')

# Incoherent correlation with data pulses
m_data_corr = np.array([
    sp.signal.correlate(
        v_rx_os,
        m_pulses_os[wf.v_carriers[idx_carrier], :],
        mode='same',
        method='fft'
    )
    for idx_carrier in range(len(wf.v_carriers))
])
v_data_lxc = np.zeros_like(v_pilot_corr) # Incoherent correlation with data
for lag in range(len(v_data_lxc) - n_spp_os):
    lixc = 0
    for idx_carrier in range(wf.p["n_bits_per_frame"]):
         ixc = m_data_corr[idx_carrier, lag+n_spp_os] / m_data_corr[idx_carrier, lag] # How much energy is in the data carrier relative to the pilot carrier?
         lixc += missing_data_carrier_penalty*np.log(np.clip(np.abs(ixc), 1e-10, 1.0)) # Penalize low energy data carriers
    v_data_lxc[lag] = lixc # Penalize low energy data carriers

# Combine coherent and incoherent correlations
v_likelihood = np.abs(v_pilot_corr) + v_data_lxc # Likelihood that the frame starts at this lag
b, a = sp.signal.butter(2, 1e-4, btype='high')  # High-pass filter the likelihood 
v_likelihood = sp.signal.filtfilt(b, a, v_likelihood)
b, a = sp.signal.butter(2, 0.5, btype='low')  # Low-pass filter the likelihood 
v_likelihood = sp.signal.filtfilt(b, a, v_likelihood)

# Progress through the sample to find frames 
m_dec = np.empty(0)
idx_lag = 0
v_idx_max = []  # Initialize vector to store all idx_max values
while idx_lag < len(v_likelihood)-n_winlen-n_winshift:
    idx_max = idx_lag + np.argmax(v_likelihood[idx_lag:idx_lag + n_winlen])
    idx_lag = max(idx_max - n_spp_os // 2, 0) # Shift to the beginning of the pilot pulse
    v_this_frame = v_rx_os[idx_lag:idx_lag+2*n_spp_os]
    v_this_pilot = v_this_frame[:n_spp_os]
    v_this_data = v_this_frame[n_spp_os:]
    m_this_pilot = np.sum(v_this_pilot * m_pulses_os[wf.v_carriers, :], axis=1)
    m_this_data = np.sum(v_this_data * m_pulses_os[wf.v_carriers, :], axis=1)
    v_dec = m_this_pilot * m_this_data
    m_dec = np.append(m_dec, v_dec)
    v_idx_max.append(idx_max)
    idx_lag += n_winshift # Move past this frame

v_dec = m_dec.flatten()
# Load the original data
with open("wf_data.txt", "r") as f:
    v_orig = np.array([int(bit) for bit in f.read().strip()])

# Convert v_dec to binary decisions
v_dec_binary = np.array([1 if x > 0 else 0 for x in v_dec])

# Save decoded binary data to a text file
with open("decoded_data.txt", "w") as f:
    for bit in v_dec_binary:
        f.write(f"{bit}")

# Calculate correlation
correlation = np.correlate(v_orig*2-1, v_dec_binary*2-1, mode='full')

# Plot correlation
plt.figure(figsize=(12, 6))
plt.plot(correlation)
plt.title('Correlation between Original and Decoded Data')
plt.xlabel('Lag')
plt.ylabel('Correlation')
plt.grid(True)
plt.show()
print(max(correlation))

plt.figure(figsize=(12, 6))
plt.plot(v_data_lxc, label='Data Correlation')
plt.plot(v_likelihood, label='Likelihood')
for idx in v_idx_max:
    plt.axvline(x=idx, color='r', linestyle='--', alpha=0.3)

plt.title('Correlation and Log Likelihood')
plt.xlabel('Sample Index')
plt.ylabel('Amplitude')
plt.legend()
#plt.xlim(0, 000)
plt.grid(True)
plt.show()

# Compute and plot STFT of v_rx
f, t, Zxx = sp.signal.stft(re2cx(v_rx), fs=wf.p["fs"]/2, nperseg=1024, noverlap=512)
plt.figure(figsize=(42, 6))
plt.pcolormesh(t, f, np.log10(np.maximum(np.abs(Zxx), 1e-10)), shading='gouraud')
plt.title('STFT of Received Signal')
plt.ylabel('Frequency [Hz]')
plt.xlabel('Time [sec]')
plt.colorbar(label='Magnitude')
plt.grid(True)
plt.show()
