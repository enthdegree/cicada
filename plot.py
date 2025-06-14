""" Plotting and processing functions for audio signals. """
import numpy as np  # Used for numerical operations and FFT
import scipy as sp  # Used for signal processing (e.g., STFT)
import matplotlib.pyplot as plt  # Used for plotting graphs
import librosa.display  # Used for displaying spectrograms in STFT

def fft(data, output_image, fs=48000):
    n_fft = 2**16
    win = np.hamming(n_fft+1)
    fft_samples = np.fft.fft(data[0:n_fft] * win[0:n_fft])  # Apply Hamming window and compute FFT
    fft_magnitude = 20 * np.log10(np.abs(fft_samples))  # Compute the magnitude in dB
    fft_freqs = np.fft.fftfreq(n_fft, d=1/fs)  # Compute the frequency bins
    plt.figure(figsize=(10, 6))
    plt.plot(fft_freqs, fft_magnitude)
    plt.title("FFT")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Magnitude (dB Power)")
    plt.grid()
    plt.savefig(output_image)
    plt.close()

def stft(data, output_image, fs=44100, nfft=2048):
    stft_sam = sp.signal.stft(data.astype(np.complex64), fs=fs, nperseg=nfft/2, noverlap=nfft/4, nfft=nfft)[2]
    plt.figure(figsize=(10, 6))
    librosa.display.specshow(20*np.log10(np.abs(stft_sam)), sr=fs, hop_length=512, x_axis='time', cmap='viridis')
    plt.title("STFT")
    plt.clim(-60, 60)
    plt.colorbar(format='%+2.0f dB')
    plt.savefig(output_image)
    plt.close()

def wf(data, output_image, fs=48000, nsam=300): # Real waveform
    data = data.astype(np.float32)
    plt.figure(figsize=(10, 6))
    plt.plot(np.arange(len(data)) / fs, data)
    plt.title("Waveform")
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude")
    plt.xlim(0, nsam / fs)  # Limit x-axis to the first nsam samples
    plt.grid()
    plt.savefig(output_image)
    plt.close()