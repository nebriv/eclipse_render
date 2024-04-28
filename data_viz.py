import os
import shutil
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib
import os
import shutil
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib
import numpy as np
from io import BytesIO
import subprocess
from tqdm import tqdm
from matplotlib.ticker import FuncFormatter

matplotlib.use('Agg')  # Use the non-GUI Agg backend

desired_width_px = 728
desired_height_px = 200
dpi = 200
line_width = 2.0
y_padding = 0.1

frames_directory = 'C:\\temp\\data\\frames'
videos_directory = 'C:\\temp\\data\\videos'

sensor_colors = {
    'UVSensor': '#40A4FF',
    'IRSensor': '#C724B1',
    'Fahrenheit': '#F96815',
    'AHTHumiditySensor': '#33A1C9',
    'MPLPressureSensor': '#008000',
    'MPLTemperatureSensor': '#E74C3C',
}

def kilo_formatter(x, pos):
    """Converts large numbers to a shortened version in thousands (k)."""
    return '%1.0fk' % (x * 1e-3)

def clear_frames(dontask=False):
    if not dontask:
        if input("Are you sure you want to clear the frames directory? (y/n): ").lower() != 'y':
            print("Aborting...")
            return
    if os.path.exists(frames_directory):
        shutil.rmtree(frames_directory)
    os.makedirs(frames_directory)

def clear_videos():
    if input("Are you sure you want to clear the videos directory? (y/n): ").lower() != 'y':
        print("Aborting...")
        return
    if os.path.exists(videos_directory):
        shutil.rmtree(videos_directory)
    os.makedirs(videos_directory)

def prepare_environment():
    clear_frames()
    clear_videos()

def load_data(filepath):
    df = pd.read_csv(filepath, index_col='time', parse_dates=True)
    df = df.assign(Fahrenheit=lambda x: (9 / 5) * x['AHTTemperatureSensor'] + 32)
    df.drop(columns=['AHTTemperatureSensor'], inplace=True)
    return df


def prepare_frame_intervals(data, time_intervals, interpolation_factor):
    """ Prepare frame intervals, ensuring that the interpolated frame count fits the specified video seconds. """
    frame_intervals = []
    total_frames = 0
    for start, end, video_seconds in time_intervals:
        subset = data[start:end]
        num_points = len(subset) * interpolation_factor
        if num_points > 0:
            milliseconds_per_frame = (video_seconds * 1000) / num_points
            frame_intervals.extend([milliseconds_per_frame] * num_points)
            total_frames += num_points
    return frame_intervals, total_frames

def kilo_formatter(x, pos):
    """Converts large numbers to a shortened version in thousands (k)."""
    return '%1.0fk' % (x * 1e-3)


def interpolate_data(data, factor=5):
    """ Interpolate additional data points to increase frame count. """
    new_index = pd.date_range(start=data.index.min(), end=data.index.max(), periods=len(data) * factor)
    interpolated_data = data.reindex(data.index.union(new_index)).interpolate(method='time').loc[new_index]
    return interpolated_data


def generate_frames(data, column, frame_intervals, interpolation_factor=5):
    print(f"Generating frames for {column}, total frames: {len(data) * interpolation_factor}")


    x_min, x_max = data.index.min(), data.index.max()
    y_min, y_max = data[column].min(), data[column].max()

    # Add some padding
    x_min -= 0.02 * (x_max - x_min)
    x_max += 0.02 * (x_max - x_min)

    y_range = y_max - y_min
    y_min -= 0.3 * y_range
    y_max += 0.4 * y_range

    tick_interval = np.ceil((y_max - y_min) / 5) # number of ticks on the Y axis
    y_ticks = np.arange(np.floor(y_min / tick_interval) * tick_interval,
                        np.ceil(y_max / tick_interval) * tick_interval,
                        tick_interval)
    frame_buffers = []

    if column == 'IRSensor':
        formatter = FuncFormatter(kilo_formatter)

    for i in tqdm(range(len(data) * interpolation_factor), desc=f"Rendering frames for {column}"):
        index = i // interpolation_factor
        fig, ax = plt.subplots(figsize=(desired_width_px / dpi, desired_height_px / dpi))
        ax.plot(data.index[:index + 1], data[column][:index + 1], lw=line_width, color=sensor_colors[column])
        ax.set_facecolor('black')
        fig.patch.set_facecolor('black')
        ax.spines['bottom'].set_color(sensor_colors[column])
        ax.spines['top'].set_color(sensor_colors[column])
        ax.spines['right'].set_color(sensor_colors[column])
        ax.spines['left'].set_color(sensor_colors[column])
        ax.spines['bottom'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        # ax.tick_params(axis='x', colors='white', labelbottom=False)
        ax.tick_params(axis='y', colors='white', labelsize=8)
        ax.set_yticks(y_ticks)

        if column == 'IRSensor':
            ax.yaxis.set_major_formatter(formatter)

        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)

        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=dpi)
        plt.close(fig)
        buf.seek(0)
        frame_buffers.append((buf, f"{frames_directory}/{column}_{i:04d}.png"))

    for buf, filename in frame_buffers:
        with open(filename, 'wb') as f:
            f.write(buf.getvalue())
        buf.close()

    return [(filename, interval) for filename, interval in zip([fb[1] for fb in frame_buffers], frame_intervals)]


def stitch_video(frame_filenames, frame_intervals, output_path, interpolation_factor=1):
    with open('frame_list.txt', 'w') as f:
        for filename, interval in zip(frame_filenames, frame_intervals):
            f.write(f"file '{filename}'\n")
            f.write(f"duration {interval / 1000}\n")
        f.write(f"file '{frame_filenames[-1]}'\n")
        f.write(f"duration {frame_intervals[-1] / 1000}\n")

    num_interpolated_frames = len(frame_filenames) * (interpolation_factor - 1)

    total_frames = len(frame_filenames) + num_interpolated_frames
    print(f"Total frames: {total_frames}")

    if interpolation_factor > 1:
        os.system(f"ffmpeg -threads 32 -f concat -safe 0 -i frame_list.txt "
                  f"-vf minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir -r 30 -vsync vfr "
                  f"-pix_fmt yuv420p -frames:v {total_frames} {output_path}")
    else:
        os.system(f"ffmpeg -threads 32 -f concat -safe 0 -i frame_list.txt -r 30 -vsync vfr -pix_fmt yuv420p {output_path}")


def get_frame_filenames():
    return [f"{frames_directory}/{f}" for f in os.listdir(frames_directory) if f.endswith('.png')]

def animate_data(filepath, time_intervals, skip_frame_generation=False):
    data = load_data(filepath)
    interpolation_factor = 5


    for column in data.columns:
        if not skip_frame_generation:
            clear_frames(dontask=True)
            interpolated_data = interpolate_data(data[[column]], factor=interpolation_factor)
            print(f"Interpolated data for {column}: {len(interpolated_data)}")
            frame_intervals, total_frames = prepare_frame_intervals(interpolated_data, time_intervals, interpolation_factor)
            total_video_seconds = sum(frame_intervals) / 1000
            print(f"Total video duration for {column}: {total_video_seconds} seconds")
            print(f"Total frames for {column}: {total_frames}")

            frame_filenames = []
            for filename, interval in generate_frames(interpolated_data, column, frame_intervals, interpolation_factor):
                frame_filenames.append(filename)
        else:
            frame_filenames = get_frame_filenames()
            frame_intervals = [1000] * len(frame_filenames)

        output_path = f"{videos_directory}/{column}_animation.mp4"
        stitch_video(frame_filenames, frame_intervals, output_path, interpolation_factor=1)


if __name__ == "__main__":
    filepath = 'resampled_data.csv'

    time_intervals = [
        ('2024-04-08 14:03:00', '2024-04-08 14:14:00', 3),
        ('2024-04-08 14:14:00', '2024-04-08 15:25:00', 20),
        ('2024-04-08 15:25:00', '2024-04-08 15:29:00', 56),
        ('2024-04-08 15:30:00', '2024-04-08 16:16:00', 13)
    ]

    # prepare_environment()
    clear_videos()
    animate_data(filepath, time_intervals, skip_frame_generation=False)
