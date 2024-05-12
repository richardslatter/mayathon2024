import os
import json
import pandas as pd
from datetime import datetime, timedelta

# Function to round datetime to the nearest hour
def round_to_nearest_hour(dt):
    return (dt + timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)

# Function to read JSON backups and organize the data
def process_backups(directory):
    backup_files = sorted(os.listdir(directory))
    athlete_points = {}
    backup_times = []

    for file in backup_files:
        if file.endswith(".json"):
            file_parts = file[:-5].split('_')  # Remove .json extension and split
            backup_time = datetime.strptime('_'.join(file_parts[1:3]), "%Y-%m-%d_%H-%M-%S")
            rounded_backup_time = round_to_nearest_hour(backup_time).strftime("%b %d %I%p")
            backup_times.append(rounded_backup_time)

            with open(os.path.join(directory, file), 'r') as f:
                data = json.load(f)

            for member_id, total_distances in data['total_distances'].items():
                athlete_name = f"{data['members'][member_id]['firstname']} {data['members'][member_id]['lastname']}"
                total_points = total_distances['total_points']
                if athlete_name not in athlete_points:
                    athlete_points[athlete_name] = {time: 0 for time in backup_times}  # Initialize with zeros for all backup times
                athlete_points[athlete_name][rounded_backup_time] = total_points

    return backup_times, athlete_points

# Function to create DataFrame and write to Excel
def write_to_excel(backup_times, athlete_points, output_file):
    df = pd.DataFrame(athlete_points).transpose().fillna(0)  # Fill NaN values with 0

    writer = pd.ExcelWriter(output_file, engine='openpyxl')
    df.to_excel(writer, index=True)
    writer._save()

# Directory containing JSON backups
backup_directory = 'backups/'

# Output Excel file
output_excel_file = 'athlete_points.xlsx'

# Process backups and write to Excel
backup_times, athlete_points = process_backups(backup_directory)
write_to_excel(backup_times, athlete_points, output_excel_file)
