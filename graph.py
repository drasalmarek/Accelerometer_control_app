import csv
import matplotlib.pyplot as plt
import numpy as np
import pywt

t_data = []
x_data = []
y_data = []
z_data = []
    
try:
    with open("output_adxl_data.csv", 'r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header if present
            
        for row in reader:
            if len(row) >= 4:
                t_data.append(float(row[0]))
                x_data.append(float(row[1]))
                y_data.append(float(row[2]))
                z_data.append(float(row[3]))

    """
    t_data = np.array(t_data[3200*5:3200*10])  # Limit to 5 to 10 seconds
    x_data = np.array(x_data[3200*5:3200*10])
    y_data = np.array(y_data[3200*5:3200*10])
    z_data = np.array(z_data[3200*5:3200*10])
    """

    font_size_axes = 22
    font_size_title = 24

    plt.figure(figsize=(19, 4))
    #plt.subplot(3, 1, 1)
    plt.plot(t_data, np.array(y_data)/2048, linestyle='-', linewidth=.5, color='blue')
    plt.xlabel('Čas [s]', fontsize=font_size_axes)
    plt.ylabel('Zrychlení [g]', fontsize=font_size_axes)
    plt.title('Signál v časové oblasti', fontsize=font_size_title)
    plt.tick_params(axis='both', labelsize=font_size_axes)
    plt.grid(True)
    
    plt.figure(figsize=(19, 4))
    #plt.subplot(3, 1, 2)
    plt.magnitude_spectrum(np.array(y_data)/2048, Fs=3200, scale='dB', linewidth=.5, color='blue')
    plt.xscale('log')
    plt.xlabel('Frekvence [Hz]', fontsize=font_size_axes)
    plt.ylabel('Amplituda [dB re 1g]', fontsize=font_size_axes)
    plt.tick_params(axis='both', labelsize=font_size_axes)
    plt.title('Signál ve frekvenční oblasti (spektrum)', fontsize=font_size_title)

    plt.figure(figsize=(19, 4))
    #plt.subplot(3, 1, 3)
    NFFT = 2048*2
    n_overlap = 64
    vmin = -80
    vmax = 0
    f_display_limit_low = 1
    f_display_limit_high = 1600
    Sxx, f, t, _ = plt.specgram(np.array(y_data)/2048, NFFT=NFFT, Fs=3200, noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma', vmin=vmin, vmax=vmax)
    cbar = plt.colorbar(label='Amplituda [dB re 1g]')
    cbar.ax.tick_params(labelsize=font_size_axes)
    cbar.set_label('Amplituda [dB re 1g]', fontsize=font_size_axes)
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frekvence [Hz]', fontsize=font_size_axes)
    plt.xlabel('Čas [s]', fontsize=font_size_axes)
    plt.tick_params(axis='both', labelsize=font_size_axes)
    plt.title('Signál v časově-frekvenční oblasti (spektrogram)', fontsize=font_size_title)

    plt.tight_layout()
    plt.show()

    """
    plt.figure(figsize=(10, 6))
    plt.subplot(2, 1, 1)
    NFFT = 2048*2
    n_overlap = 64
    vmin = -80
    vmax = 0
    f_display_limit_low = 1
    f_display_limit_high = 1600
    Sxx, f, t, _ = plt.specgram(np.array(y_data)/2048, NFFT=NFFT, Fs=3200, noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma', vmin=vmin, vmax=vmax)
    plt.colorbar(label='Amplituda [dB re 1g]')
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frekvence [Hz]')
    plt.xlabel('Čas [s]')
    plt.title('Signál v časově-frekvenční oblasti (spektrogram)')

    plt.subplot(2, 1, 2)
    fs = 3200
    signal = np.array(y_data) / 2048

    wavelet = 'cmor1.5-1.0'

    frequencies = np.logspace(np.log10(1), np.log10(1600), 48)
    scales = pywt.central_frequency(wavelet) * fs / frequencies

    from scipy.signal import decimate
    decim = 1
    if decim > 1:
        signal_ds = decimate(signal, decim, ftype='fir')
        fs_ds = fs / decim
    else:
        signal_ds = signal
        fs_ds = fs

    coeffs, freqs = pywt.cwt(
        signal_ds,
        scales,
        wavelet,
        sampling_period=1/fs_ds
    )

    power = 20 * np.log10(np.abs(coeffs) + 1e-12)

    #from scipy.ndimage import median_filter
    #power = median_filter(power, size=(3, 5))

    t = np.arange(len(signal_ds)) / fs_ds

    plt.pcolormesh(
        t,
        freqs,
        power,
        shading='auto',
        cmap='plasma',
        vmin=-40,
        vmax=0
    )
    plt.yscale('log')
    plt.ylim(1, 1600)
    plt.colorbar(label='Magnitude [dB re 1g]')
    plt.xlabel('Time [s]')
    plt.ylabel('Frequency [Hz]')
    plt.title('Scalogram - CWT (properly scaled)')

    plt.tight_layout()
    plt.show()
    """

except FileNotFoundError:
    print("File 'output_adxl_data.csv' not found.")
except ValueError:
    print("Error: CSV file contains non-numeric values.")