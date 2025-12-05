import struct
import csv
import numpy as np
import os

import matplotlib.pyplot as plt

x_array = np.array([])
y_array = np.array([])
z_array = np.array([])

sensor_data = {
    'adxl' : {
        'x' : [],
        'y' : [],
        'z' : [],
        'timestamps' : [],
        'sampling_rates' : [],
        'avg_sampling_rate' : 0
    },

    'bno' : {
        'x' : [],
        'y' : [],
        'z' : [],
        'timestamps' : [],
        'sampling_rates' : [],
        'avg_sampling_rate' : 0
    }
}

def bin_to_csv(bin_file_path):
    with open(bin_file_path, 'rb') as bin_file:
        first_header = bin_file.read(4)
        # HAL_GetTick() is a uint32_t copied with memcpy — assume little-endian
        start_time = struct.unpack('<I', first_header)[0]
        print(f"start_time_ms = {start_time}")

        while True:

            header = bin_file.read(9)
            if len(header) < 9:
                break
            index = header[0]
            timestamp = struct.unpack('<I', header[1:5])[0]
            data_size = struct.unpack('<I', header[5:9])[0]
            print(f"Index: {index}, Timestamp: {timestamp}, Data size: {data_size}, {data_size/6} samples")

            if index == 1:
                start_time = sensor_data['adxl']['timestamps'][-1] if sensor_data['adxl']['timestamps'] else start_time
                sensor_data['adxl']['timestamps'].append(timestamp)
                sampling_rate = (data_size / 6) / ((timestamp - start_time) / 1000)
                sensor_data['adxl']['sampling_rates'].append(sampling_rate)

                for _ in range(data_size//6):
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    # Unpack 6 uint8_t values
                    u = struct.unpack('6B', bytes_read)
                    # Convert to 3 int16_t values (little-endian)
                    i1 = (u[1] << 8) | u[0]
                    i2 = (u[3] << 8) | u[2]
                    i3 = (u[5] << 8) | u[4]
                    # Interpret as signed int16
                    i1 = struct.unpack('<h', struct.pack('<H', i1))[0]
                    i2 = struct.unpack('<h', struct.pack('<H', i2))[0]
                    i3 = struct.unpack('<h', struct.pack('<H', i3))[0]
                    #writer.writerow([i1, i2, i3])

                    sensor_data['adxl']['x'].append(i1)
                    sensor_data['adxl']['y'].append(i2)
                    sensor_data['adxl']['z'].append(i3)

            elif index == 2:
                start_time = sensor_data['bno']['timestamps'][-1] if sensor_data['bno']['timestamps'] else start_time
                sensor_data['bno']['timestamps'].append(timestamp)
                sampling_rate = (data_size / 6) / ((timestamp - start_time) / 1000)
                sensor_data['bno']['sampling_rates'].append(sampling_rate)

                for _ in range(data_size//6):
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    # Unpack 6 uint8_t values
                    u = struct.unpack('6B', bytes_read)
                    # Convert to 3 int16_t values (little-endian)
                    i1 = (u[1] << 8) | u[0]
                    i2 = (u[3] << 8) | u[2]
                    i3 = (u[5] << 8) | u[4]
                    # Interpret as signed int16
                    i1 = struct.unpack('<h', struct.pack('<H', i1))[0]
                    i2 = struct.unpack('<h', struct.pack('<H', i2))[0]
                    i3 = struct.unpack('<h', struct.pack('<H', i3))[0]
                    #writer.writerow([i1, i2, i3])
            
                    sensor_data['bno']['x'].append(i1)
                    sensor_data['bno']['y'].append(i2)
                    sensor_data['bno']['z'].append(i3)
            

    # Calculate average sampling rates
    if sensor_data['adxl']['sampling_rates']:
        sensor_data['adxl']['avg_sampling_rate'] = sum(sensor_data['adxl']['sampling_rates']) / len(sensor_data['adxl']['sampling_rates'])
        print(f"ADXL Average Sampling Rate: {sensor_data['adxl']['avg_sampling_rate']} Hz")
    if sensor_data['bno']['sampling_rates']:
        sensor_data['bno']['avg_sampling_rate'] = sum(sensor_data['bno']['sampling_rates']) / len(sensor_data['bno']['sampling_rates'])
        print(f"BNO Average Sampling Rate: {sensor_data['bno']['avg_sampling_rate']} Hz")

    # write to CSV
    adxl_file = os.path.join(os.path.dirname(__file__), 'output_adxl_data.csv')
    with open(adxl_file, 'w', newline='') as adxl_csvfile:
        writer = csv.writer(adxl_csvfile)
        writer.writerow(['t', 'X', 'Y', 'Z'])
        for i in range(len(sensor_data['adxl']['x'])):
            writer.writerow([i / sensor_data['adxl']['avg_sampling_rate'], sensor_data['adxl']['x'][i], sensor_data['adxl']['y'][i], sensor_data['adxl']['z'][i]])
        
    bno_file = os.path.join(os.path.dirname(__file__), 'output_bno_data.csv')
    with open(bno_file, 'w', newline='') as bno_csvfile:
        writer = csv.writer(bno_csvfile)
        writer.writerow(['t', 'X', 'Y', 'Z'])
        for i in range(len(sensor_data['bno']['x'])):
            writer.writerow([i / sensor_data['bno']['avg_sampling_rate'], sensor_data['bno']['x'][i], sensor_data['bno']['y'][i], sensor_data['bno']['z'][i]])

    plt.figure(1, figsize=(12, 6))
    plt.subplot(2, 1, 1)
    t = [i / sensor_data['adxl']['avg_sampling_rate'] for i in range(len(sensor_data['adxl']['x']))]  # Assuming a sampling rate of 3200 Hz for ADXL
    plt.plot(t, sensor_data['adxl']['x'], label='ADXL X-axis', color='r')
    plt.plot(t, sensor_data['adxl']['y'], label='ADXL Y-axis', color='g')
    plt.plot(t, sensor_data['adxl']['z'], label='ADXL Z-axis', color='b')
    plt.xlabel('Sample Number')
    plt.ylabel('Acceleration')
    plt.title('ADXL Accelerometer Data')
    plt.legend()
    plt.grid(True)
    plt.subplot(2, 1, 2)
    t = [i / sensor_data['bno']['avg_sampling_rate'] for i in range(len(sensor_data['bno']['x']))]  # Assuming a sampling rate of 100 Hz for BNO
    plt.plot(t, sensor_data['bno']['x'], label='BNO X-axis', color='r')
    plt.plot(t, sensor_data['bno']['y'], label='BNO Y-axis', color='g')
    plt.plot(t, sensor_data['bno']['z'], label='BNO Z-axis', color='b')
    plt.xlabel('Sample Number')
    plt.ylabel('Acceleration')
    plt.title('BNO Accelerometer Data')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # computing STFT on ADXL data
    NFFT = 2048
    n_overlap = 64
    f_display_limit_low = 10
    f_display_limit_high = sensor_data['adxl']['avg_sampling_rate'] / 2
    plt.figure(2, figsize=(16, 9))
    plt.subplot(3, 1, 1)
    Sxx, f, t, _ = plt.specgram(np.array(sensor_data['adxl']['x']), NFFT=NFFT, Fs=sensor_data['adxl']['avg_sampling_rate'], noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma')
    plt.colorbar(label='Intensity [dB]')
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('X axis STFT')

    plt.subplot(3, 1, 2)
    Sxx, f, t, _ = plt.specgram(np.array(sensor_data['adxl']['y']), NFFT=NFFT, Fs=sensor_data['adxl']['avg_sampling_rate'], noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma')
    plt.colorbar(label='Intensity [dB]')
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('Y axis STFT')

    plt.subplot(3, 1, 3)
    Sxx, f, t, _ = plt.specgram(np.array(sensor_data['adxl']['z']), NFFT=NFFT, Fs=sensor_data['adxl']['avg_sampling_rate'], noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma')
    plt.colorbar(label='Intensity [dB]')
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('Z axis STFT')

    plt.tight_layout()
    plt.show()

    # plotting spectrum
    plt.figure(3, figsize=(12, 6))
    plt.subplot(3, 1, 1)
    plt.magnitude_spectrum(np.array(sensor_data['adxl']['x']), Fs=sensor_data['adxl']['avg_sampling_rate'], scale='dB', color='r')
    plt.title('ADXL X-axis Spectrum')
    plt.xscale('log')

    plt.subplot(3, 1, 2)
    plt.magnitude_spectrum(np.array(sensor_data['adxl']['y']), Fs=sensor_data['adxl']['avg_sampling_rate'], scale='dB', color='g')
    plt.title('ADXL Y-axis Spectrum')   
    plt.xscale('log')

    plt.subplot(3, 1, 3)
    plt.magnitude_spectrum(np.array(sensor_data['adxl']['z']), Fs=sensor_data['adxl']['avg_sampling_rate'], scale='dB', color='b')
    plt.title('ADXL Z-axis Spectrum')
    plt.xscale('log')

    plt.tight_layout()
    plt.show()


raw_file_path = os.path.join(os.path.dirname(__file__), 'raw_data_0002.bin')
bin_to_csv(raw_file_path)