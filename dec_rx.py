""" 
Decode rx.wav 
"""
import numpy as np
import scipy as sp
import wave
import matplotlib.pyplot as plt
import wf

fname_wf = "rx.wav"
b_plot = True

# read rx
wave_rx = wave.open(fname_wf, "r")
buf_rx = wave_rx.readframes(wave_rx.getnframes())
v_rx = np.frombuffer(buf_rx, dtype=np.int16).astype(np.float64) 
wave_rx.close()

print('Correlating pulses against rx data')
n_carriers = 2*wf.params["n_hop_sequence_len"]
n_pulse_len = wf.params["n_pulse_len_re"]
n_hop_sequence_len = wf.params["n_hop_sequence_len"]
n_frame_len = n_hop_sequence_len*n_pulse_len
n_sam_to_dec = len(v_rx) # n_sam_to_dec = 12*n_frame_len
v_rx = np.concat((np.zeros(n_frame_len),v_rx[:n_sam_to_dec],np.zeros(n_frame_len)))

m_corr = np.array([
    sp.signal.correlate(
        v_rx,
        wf.m_pulses[wf.v_carriers[idx_t],:],
        mode='same',
        method='fft'
    )
    for idx_t in range(n_carriers)])
m_corr = m_corr / np.std(m_corr, axis=1, keepdims=True)

print('Building pulse likelihood map...')
n_lags = len(m_corr[0,:])

print('Calculating pulse likelihoods...')
m_noise_var = np.array([
    np.var(m_corr[:, idx_lag:(idx_lag+n_pulse_len)], axis=1)
    for idx_lag in range(n_lags - n_pulse_len)
]).T
m_query_var = np.abs(m_corr[:, n_pulse_len:(n_lags)])**2
m_pulse_likelihood = m_query_var - np.median(m_noise_var, axis=0)
b, a = sp.signal.butter(4, 0.45, btype='low')  
m_pulse_likelihood = np.array([sp.signal.filtfilt(b, a, row) for row in m_pulse_likelihood])

print('Building frame likelihood map')
m_carrier_idx = np.reshape(np.arange(n_carriers), [2,n_hop_sequence_len])
m_pulse_start_idx = n_pulse_len*np.tile(np.arange(n_hop_sequence_len),[2,1])
m_p = np.array([
    m_pulse_likelihood[m_carrier_idx, idx_lag+m_pulse_start_idx]
    for idx_lag in range(n_lags - n_frame_len)
])
v_frame_likelihood = np.sum(np.max(m_p, axis=2), axis=1)

print('Decoding frames')
n_win_len = int(n_frame_len*1.6)
n_advance_len = int(n_frame_len*0.2)
v_frame_locations = np.empty(0, dtype=int)
m_frames_soft = np.empty(0)
idx_win = 0
while(idx_win < n_lags - n_frame_len):
    idx_lag = idx_win + np.argmax(v_frame_likelihood[idx_win:idx_win+n_win_len])
    v_frame_locations = np.append(v_frame_locations, idx_lag)
    m_this_frame_likelihood = m_pulse_likelihood[m_carrier_idx, idx_lag+m_pulse_start_idx]
    v_this_frame_soft = m_this_frame_likelihood[1,:] - np.min(m_this_frame_likelihood, axis=0)
    m_frames_soft = np.vstack([m_frames_soft, v_this_frame_soft]) if m_frames_soft.size else v_this_frame_soft[np.newaxis, :]
    idx_win = idx_lag + n_advance_len
v_bits_soft = m_frames_soft.flatten()
v_bits = (v_bits_soft > 0).astype(np.int32)
with open("decoded_data.txt", "w") as f: # Save decoded binary data to a text file
    for bit in v_bits:
        f.write(f"{bit}")

print('Comparing to original data')
with open("wf_data.txt", "r") as f:
    v_bits_true = np.array([int(bit) for bit in f.read().strip()])
v_bit_correlation = np.correlate(v_bits*2-1, v_bits_true*2-1, mode='full')
idx_lag = np.argmax(v_bit_correlation)
n_err = (len(v_bits_true)-np.max(v_bit_correlation))/2
v_bits_maxcorr = v_bits[idx_lag-len(v_bits_true)+1:idx_lag+1]
print(f'ber: {n_err/len(v_bits_true)} ({n_err}/{len(v_bits_true)})')
v_idx_err = np.nonzero(np.abs(v_bits_maxcorr-v_bits_true[:len(v_bits_maxcorr)]))

# Calculate the frames that contain the maxcorr bits
idx_startframe = int((idx_lag-len(v_bits_true)+1) / n_hop_sequence_len)
idx_endframe = int((idx_lag+1) / n_hop_sequence_len)

if(b_plot):
    # Plot STFT of the samples
    # Create a subplot with the frame errors above the STFT plot
    fig, axs = plt.subplots(2, 1, figsize=(30, 15), gridspec_kw={'height_ratios': [1, 3]})

    # Frame errors plot
    v_err = v_bits_true[:len(v_bits_maxcorr)] - v_bits_maxcorr
    axs[0].plot(v_err, label="diff", alpha=0.7)
    for idx in range(0, len(v_bits_true[:len(v_bits_maxcorr)]), n_hop_sequence_len):
        axs[0].axvline(x=idx, color='gray', linestyle='--', alpha=0.5, label="Hop Sequence Boundary" if idx == 0 else None)
    axs[0].set_title("Frame Errors")
    axs[0].set_xlabel("Bit Index")
    axs[0].set_ylabel("Value")
    axs[0].legend()
    axs[0].grid()
    
    # Heatmap of m_pulse_likelihood
    m_this_frame = m_pulse_likelihood[:,v_frame_locations[idx_startframe]:v_frame_locations[idx_endframe]]
    pcm = axs[1].imshow(
        np.log10(np.maximum(1e-10,m_this_frame)), 
        aspect='auto', cmap='viridis', 
        extent=[0, m_this_frame.shape[1], 0, n_carriers], vmin=-10, vmax=0)
    for idx_err in v_idx_err[0]:
        axs[1].axvline(
            x=idx_err * m_this_frame.shape[1] / len(v_err), 
            color='red', linestyle='-', linewidth=5, alpha=0.7, label="Error Location" if idx_err == v_idx_err[0][0] else None
        )
    axs[1].legend()
    axs[1].set_title("Heatmap of Pulse Likelihood Matrix (m_pulse_likelihood)")
    axs[1].set_xlabel("Lag idx")
    axs[1].set_ylabel("Carrier Index")
    fig.colorbar(pcm, ax=axs[1], label="Pulse Likelihood Magnitude")

    plt.tight_layout()
    plt.show()

    # Histogram of error locations modulo n_hop_sequence_len
    plt.figure(figsize=(10, 6))
    plt.hist(v_idx_err[0] % n_hop_sequence_len, bins=n_hop_sequence_len, alpha=0.7, edgecolor='black')
    plt.title("Histogram of Error locations Modulo Hop Sequence Length")
    plt.xlabel("Error Index Modulo Hop Sequence Length")
    plt.ylabel("Frequency")
    plt.grid()
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.plot(v_frame_likelihood, label="Frame Start Likelihood")
    plt.title("Frame Start Likelihood")
    plt.xlabel("Lag")
    plt.ylabel("Likelihood")
    plt.legend()
    plt.grid()
    plt.show()

    # Plot v_bit_correlation
    plt.figure(figsize=(10, 6))
    plt.plot(v_bit_correlation, label="Bit Correlation")
    plt.title("Bit Correlation")
    plt.xlabel("Lag")
    plt.ylabel("Correlation")
    plt.legend()
    plt.grid()
    plt.show()