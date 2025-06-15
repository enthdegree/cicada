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

print('Building pulse likelihood map...')
m_pulse_likelihood = np.full(m_corr.shape, np.nan) 
n_lags = len(m_corr[0,:])

print('Calculating pulse likelihoods...')
m_noise_var = np.array([
    np.var(m_corr[:, idx_lag:(idx_lag+n_pulse_len)], axis=1)
    for idx_lag in range(n_lags - n_pulse_len)
]).T
m_query_var = np.abs(m_corr[:, n_pulse_len:(n_lags)])**2
m_pulse_likelihood[:, :n_lags - n_pulse_len] = m_query_var - np.median(m_noise_var, axis=0)

print('Building frame likelihood map')
m_carrier_idx = np.reshape(np.arange(n_carriers), [2,n_hop_sequence_len])
m_pulse_start_idx = n_pulse_len*np.tile(np.arange(n_hop_sequence_len),[2,1])
v_frame_likelihood = np.full(n_lags, np.nan)
# Vectorized computation for frame start likelihood
m_p = np.array([
    m_pulse_likelihood[m_carrier_idx, idx_lag+m_pulse_start_idx]
    for idx_lag in range(n_lags - n_frame_len)
])
v_frame_likelihood[:n_lags - n_frame_len] = np.sum(np.max(m_p, axis=2), axis=1)

print('Decoding frames')
n_win_len = int(n_frame_len*1.2)
n_advance_len = int(n_frame_len*0.4)
v_frame_locations = np.empty(0)
m_frames_soft = np.empty(0)
idx_win = 0
v_likelihood_win = sp.signal.windows.gaussian(n_win_len, std=0.1)
while(idx_win < n_lags - n_frame_len):
    idx_lag = idx_win + np.argmax(v_frame_likelihood[idx_win:idx_win+n_win_len])
    v_frame_locations = np.append(v_frame_locations, idx_lag)
    m_this_frame_likelihood = m_pulse_likelihood[m_carrier_idx, idx_lag+m_pulse_start_idx]
    v_this_frame_soft = m_this_frame_likelihood[1,:] - np.mean(m_this_frame_likelihood, axis=0)
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
v_idx_err = np.nonzero(np.abs(v_bits_maxcorr-v_bits_true))

if(b_plot):
    # Histogram of error locations modulo n_hop_sequence_len
    plt.figure(figsize=(10, 6))
    plt.hist(v_idx_err[0][23:] % n_hop_sequence_len, bins=n_hop_sequence_len, alpha=0.7, edgecolor='black')
    plt.title("Histogram of Error locations Modulo Hop Sequence Length")
    plt.xlabel("Error Index Modulo Hop Sequence Length")
    plt.ylabel("Frequency")
    plt.grid()
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.plot(v_frame_likelihood, label="Frame Start Likelihood")
    for frame_location in v_frame_locations:
        plt.axvline(x=frame_location, color='red', linestyle='--', alpha=0.7, label="Frame Location")
    plt.title("Frame Start Likelihood")
    plt.xlabel("Lag")
    plt.ylabel("Likelihood")
    plt.legend()
    plt.grid()
    plt.show()

    plt.figure(figsize=(10, 6))
    plt.plot(abs(v_bits_maxcorr-v_bits_true[:len(v_bits_maxcorr)]), label="diff", alpha=0.7)
    plt.xlabel("Bit Index")
    plt.ylabel("Value")
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
