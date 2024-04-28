import pandas as pd
import numpy as np

# Load data
data = pd.read_csv('eclipse_sensor_data_viz_columns.csv', parse_dates=['time'])

# Define time intervals and corresponding desired elapsed video time in seconds
time_intervals = [
    ('2024-04-08 14:03:00', '2024-04-08 14:14:00', 3),
    ('2024-04-08 14:14:00', '2024-04-08 15:25:00', 25),
    ('2024-04-08 15:25:00', '2024-04-08 15:29:00', 47),
    ('2024-04-08 15:30:00', '2024-04-08 16:16:00', 17)
]

# Initialize an empty DataFrame to hold the resampled data
resampled_data = pd.DataFrame()

for start, end, video_seconds in time_intervals:
    mask = (data['time'] >= start) & (data['time'] < end)
    interval_data = data.loc[mask]

    # Calculate the time span in seconds of the data interval
    time_span_seconds = (pd.to_datetime(end) - pd.to_datetime(start)).total_seconds()

    # Calculate the number of data points that should be taken to fit the video duration
    total_data_points = len(interval_data)
    data_points_needed = total_data_points * video_seconds / time_span_seconds

    # Calculate the sampling interval as the ratio of available data points to needed points
    sampling_interval = int(total_data_points / data_points_needed)

    # Resample the data based on calculated interval
    resampled_interval_data = interval_data.iloc[::sampling_interval]
    resampled_data = pd.concat([resampled_data, resampled_interval_data], ignore_index=True)

# Save the resampled data to a new CSV
resampled_data.to_csv('resampled_data.csv', index=False)
