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
        'acc_x' : [],
        'acc_y' : [],
        'acc_z' : [],
        'gyr_x' : [],
        'gyr_y' : [],
        'gyr_z' : [],
        'mag_x' : [],
        'mag_y' : [],
        'mag_z' : [],
        'eul_heading' : [],
        'eul_roll' : [],
        'eul_pitch' : [],
        'quat_w' : [],
        'quat_x' : [],
        'quat_y' : [],
        'quat_z' : [],
        'lia_x' : [],
        'lia_y' : [],
        'lia_z' : [],
        'grv_x' : [],
        'grv_y' : [],
        'grv_z' : [],
        'temp' : [],
        'single_size' : (6*3 + 6 + 8 + 6 + 6 + 1),

        'timestamps' : [],
        'sampling_rates' : [],
        'avg_sampling_rate' : 0
    },

    'adc0' : {
        'values' : [],
        'timestamps' : [],
        'sampling_rates' : [],
        'avg_sampling_rate' : 0
    }
}

def bytes_to_data(bytes_read, number_of_values):
    # Unpack 6 uint8_t values
    u = struct.unpack(f'{number_of_values*2}B', bytes_read)
    output = []
    for i in range(0, number_of_values):
        val = (u[i*2 + 1] << 8) | u[i*2]
        # Interpret as signed int16
        val = struct.unpack('<h', struct.pack('<H', val))[0]
        output.append(val)
    return output


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
            print(f"Index: {index}, Timestamp: {timestamp}, Data size: {data_size}")

            if index == 1:
                start_time = sensor_data['adxl']['timestamps'][-1] if sensor_data['adxl']['timestamps'] else start_time
                sensor_data['adxl']['timestamps'].append(timestamp)
                sampling_rate = (data_size / 6) / ((timestamp - start_time) / 1000)
                sensor_data['adxl']['sampling_rates'].append(sampling_rate)

                for _ in range(data_size//6):
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['adxl']['x'].append(data[0])
                    sensor_data['adxl']['y'].append(data[1])
                    sensor_data['adxl']['z'].append(data[2])

            elif index == 2:
                start_time = sensor_data['bno']['timestamps'][-1] if sensor_data['bno']['timestamps'] else start_time
                sensor_data['bno']['timestamps'].append(timestamp)
                sampling_rate = (data_size / sensor_data['bno']['single_size']) / ((timestamp - start_time) / 1000)
                sensor_data['bno']['sampling_rates'].append(sampling_rate)

                for _ in range(data_size//sensor_data['bno']['single_size']):
                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['acc_x'].append(data[0])
                    sensor_data['bno']['acc_y'].append(data[1])
                    sensor_data['bno']['acc_z'].append(data[2])

                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['gyr_x'].append(data[0])
                    sensor_data['bno']['gyr_y'].append(data[1])
                    sensor_data['bno']['gyr_z'].append(data[2])

                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['mag_x'].append(data[0])
                    sensor_data['bno']['mag_y'].append(data[1])
                    sensor_data['bno']['mag_z'].append(data[2])

                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['eul_heading'].append(data[0])
                    sensor_data['bno']['eul_roll'].append(data[1])
                    sensor_data['bno']['eul_pitch'].append(data[2])

                    bytes_read = bin_file.read(8)
                    if len(bytes_read) < 8:
                        break
                    data = bytes_to_data(bytes_read, 4)
                    sensor_data['bno']['quat_w'].append(data[0])
                    sensor_data['bno']['quat_x'].append(data[1])
                    sensor_data['bno']['quat_y'].append(data[2])
                    sensor_data['bno']['quat_z'].append(data[3])

                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['lia_x'].append(data[0])
                    sensor_data['bno']['lia_y'].append(data[1])
                    sensor_data['bno']['lia_z'].append(data[2])

                    bytes_read = bin_file.read(6)
                    if len(bytes_read) < 6:
                        break
                    data = bytes_to_data(bytes_read, 3)
                    sensor_data['bno']['grv_x'].append(data[0])
                    sensor_data['bno']['grv_y'].append(data[1])
                    sensor_data['bno']['grv_z'].append(data[2])

                    bytes_read = bin_file.read(1)
                    if len(bytes_read) < 1:
                        break
                    u = struct.unpack('1B', bytes_read)
                    sensor_data['bno']['temp'].append(u[0])

            elif index == 3:
                start_time = sensor_data['adc0']['timestamps'][-1] if sensor_data['adc0']['timestamps'] else start_time
                sensor_data['adc0']['timestamps'].append(timestamp)
                sampling_rate = (data_size) / ((timestamp - start_time) / 1000)
                sensor_data['adc0']['sampling_rates'].append(sampling_rate)

                for _ in range(data_size):
                    bytes_read = bin_file.read(1)
                    u = struct.unpack('1B', bytes_read)
                    i = struct.unpack('<h', struct.pack('<H', u[0]))[0]
                    sensor_data['adc0']['values'].append(i)

            

    # Calculate average sampling rates
    if sensor_data['adxl']['sampling_rates']:
        sensor_data['adxl']['avg_sampling_rate'] = sum(sensor_data['adxl']['sampling_rates']) / len(sensor_data['adxl']['sampling_rates'])
        print(f"ADXL Average Sampling Rate: {sensor_data['adxl']['avg_sampling_rate']} Hz")

    if sensor_data['bno']['sampling_rates']:
        sensor_data['bno']['avg_sampling_rate'] = sum(sensor_data['bno']['sampling_rates']) / len(sensor_data['bno']['sampling_rates'])
        print(f"BNO Average Sampling Rate: {sensor_data['bno']['avg_sampling_rate']} Hz")

    if sensor_data['adc0']['sampling_rates']:
        sensor_data['adc0']['avg_sampling_rate'] = sum(sensor_data['adc0']['sampling_rates']) / len(sensor_data['adc0']['sampling_rates'])
        print(f"ADC0 Average Sampling Rate: {sensor_data['adc0']['avg_sampling_rate']} Hz")

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
        writer.writerow(['t', 
                         'acc_X', 'acc_Y', 'acc_Z', 
                         'gyr_X', 'gyr_Y', 'gyr_Z', 
                         'mag_X', 'mag_Y', 'mag_Z',
                         'eul_heading', 'eul_roll', 'eul_pitch',
                         'quat_w', 'quat_x', 'quat_y', 'quat_z',
                         'lia_X', 'lia_Y', 'lia_Z',
                         'grv_X', 'grv_Y', 'grv_Z',
                         'temp'])
        for i in range(len(sensor_data['bno']['acc_x'])):
            writer.writerow([i / sensor_data['bno']['avg_sampling_rate'], 
                    sensor_data['bno']['acc_x'][i], sensor_data['bno']['acc_y'][i], sensor_data['bno']['acc_z'][i], 
                    sensor_data['bno']['gyr_x'][i], sensor_data['bno']['gyr_y'][i], sensor_data['bno']['gyr_z'][i], 
                    sensor_data['bno']['mag_x'][i], sensor_data['bno']['mag_y'][i], sensor_data['bno']['mag_z'][i],
                    sensor_data['bno']['eul_heading'][i], sensor_data['bno']['eul_roll'][i], sensor_data['bno']['eul_pitch'][i],
                    sensor_data['bno']['quat_w'][i], sensor_data['bno']['quat_x'][i], sensor_data['bno']['quat_y'][i], sensor_data['bno']['quat_z'][i],
                    sensor_data['bno']['lia_x'][i], sensor_data['bno']['lia_y'][i], sensor_data['bno']['lia_z'][i],
                    sensor_data['bno']['grv_x'][i], sensor_data['bno']['grv_y'][i], sensor_data['bno']['grv_z'][i],
                    sensor_data['bno']['temp'][i]])

    adc0_file = os.path.join(os.path.dirname(__file__), 'output_adc0_data.csv')
    with open(adc0_file, 'w', newline='') as adc0_csvfile:
        writer = csv.writer(adc0_csvfile)
        writer.writerow(['t', 'ADC0'])
        for i in range(len(sensor_data['adc0']['values'])):
            writer.writerow([i / sensor_data['adc0']['avg_sampling_rate'], sensor_data['adc0']['values'][i]])

    plt.figure(1, figsize=(12, 6))
    plt.subplot(3, 1, 1)
    t = [i / sensor_data['adxl']['avg_sampling_rate'] for i in range(len(sensor_data['adxl']['x']))]  # Assuming a sampling rate of 3200 Hz for ADXL
    plt.plot(t, sensor_data['adxl']['x'], label='ADXL X-axis', color='r')
    plt.plot(t, sensor_data['adxl']['y'], label='ADXL Y-axis', color='g')
    plt.plot(t, sensor_data['adxl']['z'], label='ADXL Z-axis', color='b')
    plt.xlabel('Time [sec]')
    plt.ylabel('Output Value')
    plt.title('ADXL Accelerometer Data')
    plt.legend()
    plt.grid(True)
    plt.subplot(3, 1, 2)
    t = [i / sensor_data['bno']['avg_sampling_rate'] for i in range(len(sensor_data['bno']['acc_x']))]  # Assuming a sampling rate of 100 Hz for BNO
    plt.plot(t, sensor_data['bno']['acc_x'], label='BNO X-axis', color='r')
    plt.plot(t, sensor_data['bno']['acc_y'], label='BNO Y-axis', color='g')
    plt.plot(t, sensor_data['bno']['acc_z'], label='BNO Z-axis', color='b')
    plt.xlabel('Time [sec]')
    plt.ylabel('Output Value')
    plt.title('BNO Accelerometer Data')
    plt.legend()
    plt.grid(True)
    plt.subplot(3, 1, 3)
    t = [i / sensor_data['adc0']['avg_sampling_rate'] for i in range(len(sensor_data['adc0']['values']))]  # Assuming a sampling rate of 100 Hz for BNO
    plt.plot(t, sensor_data['adc0']['values'], label='ADC0 values', color='r')
    plt.xlabel('Time [sec]')
    plt.ylabel('ADC value')
    plt.title('ADC0 Data')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    plt.figure(1, figsize=(12, 6))
    plt.subplot(3, 1, 1)
    t = [i / sensor_data['bno']['avg_sampling_rate'] for i in range(len(sensor_data['bno']['acc_x']))]  # Assuming a sampling rate of 3200 Hz for ADXL
    plt.plot(t, sensor_data['bno']['acc_x'], label='ADXL X-axis', color='r')
    plt.plot(t, sensor_data['bno']['acc_y'], label='ADXL Y-axis', color='g')
    plt.plot(t, sensor_data['bno']['acc_z'], label='ADXL Z-axis', color='b')
    plt.xlabel('Time [sec]')
    plt.ylabel('Output Value')
    plt.title('BNO Accelerometer Data')
    plt.legend()
    plt.grid(True)
    plt.subplot(3, 1, 2)
    t = [i / sensor_data['bno']['avg_sampling_rate'] for i in range(len(sensor_data['bno']['gyr_x']))]  # Assuming a sampling rate of 100 Hz for BNO
    plt.plot(t, sensor_data['bno']['gyr_x'], label='BNO X-axis', color='r')
    plt.plot(t, sensor_data['bno']['gyr_y'], label='BNO Y-axis', color='g')
    plt.plot(t, sensor_data['bno']['gyr_z'], label='BNO Z-axis', color='b')
    plt.xlabel('Time [sec]')
    plt.ylabel('Output Value')
    plt.title('BNO Gyroscope Data')
    plt.legend()
    plt.grid(True)
    plt.subplot(3, 1, 3)
    t = [i / sensor_data['bno']['avg_sampling_rate'] for i in range(len(sensor_data['bno']['mag_x']))]  # Assuming a sampling rate of 100 Hz for BNO
    plt.plot(t, sensor_data['bno']['mag_x'], label='BNO X-axis', color='r')
    plt.plot(t, sensor_data['bno']['mag_y'], label='BNO Y-axis', color='g')
    plt.plot(t, sensor_data['bno']['mag_z'], label='BNO Z-axis', color='b')
    plt.xlabel('Time [sec]')
    plt.ylabel('Output Value')
    plt.title('BNO Magnetometer Data')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # computing STFT on ADXL data
    NFFT = 2048*2
    n_overlap = 64
    f_display_limit_low = 10
    vmin = 0
    vmax = 60
    f_display_limit_high = sensor_data['adxl']['avg_sampling_rate'] / 2
    plt.figure(2, figsize=(16, 9))
    plt.subplot(3, 1, 1)
    Sxx, f, t, _ = plt.specgram(np.array(sensor_data['adxl']['x']), NFFT=NFFT, Fs=sensor_data['adxl']['avg_sampling_rate'], noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma', vmin=vmin, vmax=vmax)
    plt.colorbar(label='Intensity [dB]')
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('X axis STFT')

    plt.subplot(3, 1, 2)
    Sxx, f, t, _ = plt.specgram(np.array(sensor_data['adxl']['y']), NFFT=NFFT, Fs=sensor_data['adxl']['avg_sampling_rate'], noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma', vmin=vmin, vmax=vmax)
    plt.colorbar(label='Intensity [dB]')
    plt.yscale('log')  # Set frequency axis to log scale
    plt.ylim(f_display_limit_low, f_display_limit_high)  # Limit frequency axis
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('Y axis STFT')

    plt.subplot(3, 1, 3)
    Sxx, f, t, _ = plt.specgram(np.array(sensor_data['adxl']['z']), NFFT=NFFT, Fs=sensor_data['adxl']['avg_sampling_rate'], noverlap=n_overlap, scale='dB')
    plt.pcolormesh(t, f, 10 * np.log10(Sxx), shading='auto', cmap='plasma', vmin=vmin, vmax=vmax)
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


raw_file_path = os.path.join(os.path.dirname(__file__), 'raw_data_0012.bin')
bin_to_csv(raw_file_path)

# something nice in 0004, 0057