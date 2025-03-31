import pandas as pd
from pathlib import Path
import argparse

# Constants
MMOL_TO_MGDL = 18.018  # Conversion factor from mmol/L to mg/dL

def combine_notes_within_window(notes_df, window_minutes=60):
    """Combine notes that occur within a specified time window of each other."""
    if notes_df.empty:
        return notes_df
        
    # Sort notes by timestamp
    notes_df = notes_df.sort_values('Device Timestamp')
    
    # Initialize lists to store combined data
    combined_notes = []
    current_note = notes_df.iloc[0]
    current_notes = [current_note['Notes']]
    first_timestamp = current_note['Device Timestamp']
    latest_timestamp = first_timestamp
    window_end = first_timestamp + pd.Timedelta(minutes=window_minutes)
    
    # Iterate through remaining notes
    for _, note in notes_df.iloc[1:].iterrows():
        if note['Device Timestamp'] <= window_end:
            # Note is within window, add to current notes
            current_notes.append(note['Notes'])
            latest_timestamp = note['Device Timestamp']  # Update latest timestamp
        else:
            # Note is outside window, save current combined note and start new window
            combined_notes.append({
                'Device Timestamp': first_timestamp,  # First timestamp for finding initial glucose
                'Latest Timestamp': latest_timestamp,  # Latest timestamp for peak/postprandial
                'Notes': ' | '.join(current_notes),
                'Glucose': current_note['Glucose']
            })
            current_note = note
            current_notes = [note['Notes']]
            first_timestamp = note['Device Timestamp']
            latest_timestamp = first_timestamp
            window_end = first_timestamp + pd.Timedelta(minutes=window_minutes)
    
    # Add the last combined note
    combined_notes.append({
        'Device Timestamp': first_timestamp,
        'Latest Timestamp': latest_timestamp,
        'Notes': ' | '.join(current_notes),
        'Glucose': current_note['Glucose']
    })
    
    return pd.DataFrame(combined_notes)

def calculate_overnight_glucose(df):
    """Calculate average overnight glucose (midnight to 6am) for all nights in the dataset."""
    # Create a mask for overnight readings (midnight to 6am)
    overnight_mask = (df['Device Timestamp'].dt.hour >= 0) & (df['Device Timestamp'].dt.hour < 6)
    overnight_readings = df[overnight_mask]['Glucose']
    
    return overnight_readings.mean() if not overnight_readings.empty else None

def calculate_fasting_glucose(df, notes_df):
    """Calculate average fasting glucose by excluding meal windows."""
    meal_windows_mask = pd.Series(False, index=df.index)
    for _, note_row in notes_df.iterrows():
        timestamp = note_row['Device Timestamp']
        window_mask = (df['Device Timestamp'] >= timestamp) & \
                     (df['Device Timestamp'] <= timestamp + pd.Timedelta(hours=2))
        meal_windows_mask = meal_windows_mask | window_mask
    
    fasting_readings = df[~meal_windows_mask]['Glucose']
    return fasting_readings.mean() if not fasting_readings.empty else None

def find_closest_reading(df, target_time, window_minutes=15):
    """Find the closest glucose reading within a time window."""
    mask = (df['Device Timestamp'] >= target_time - pd.Timedelta(minutes=window_minutes)) & \
           (df['Device Timestamp'] <= target_time + pd.Timedelta(minutes=window_minutes))
    
    readings = df[mask]
    if readings.empty:
        return None
        
    sorted_readings = readings.iloc[
        (readings['Device Timestamp'] - target_time).abs().argsort()
    ].reset_index(drop=True)
    
    return sorted_readings.iloc[0]

def calculate_peak_glucose(df, start_time, hours=2):
    """Calculate peak glucose within a time window."""
    mask = (df['Device Timestamp'] >= start_time) & \
           (df['Device Timestamp'] <= start_time + pd.Timedelta(hours=hours))
    readings = df[mask]
    return readings['Glucose'].max() if not readings.empty else None

def calculate_postprandial_glucose(df, start_time, hours=2):
    """Calculate postprandial glucose at exactly 2 hours after start time."""
    postprandial_time = start_time + pd.Timedelta(hours=hours)
    closest_reading = find_closest_reading(df, postprandial_time)
    return closest_reading['Glucose'] if closest_reading is not None and pd.notna(closest_reading['Glucose']) else None

def calculate_delta(initial_glucose, postprandial_glucose):
    """Calculate the difference between postprandial and initial glucose."""
    if pd.notna(postprandial_glucose) and pd.notna(initial_glucose):
        return postprandial_glucose - initial_glucose
    return None

def process_meal_data(df, note_row):
    """Process data for a single meal/note entry."""
    timestamp = note_row['Device Timestamp']  # For initial glucose
    latest_timestamp = note_row.get('Latest Timestamp', timestamp)  # For peak/postprandial
    note = note_row['Notes']
    
    # Find initial glucose reading
    closest_reading = find_closest_reading(df, timestamp)
    if closest_reading is None:
        return None
        
    initial_glucose = closest_reading['Glucose']
    
    # Calculate peak and postprandial values using the latest timestamp
    peak = calculate_peak_glucose(df, latest_timestamp)
    postprandial = calculate_postprandial_glucose(df, latest_timestamp)
    delta = calculate_delta(initial_glucose, postprandial)
    
    return {
        'Timestamp': timestamp,
        'Note': note,
        'Initial Glucose (mmol/L)': initial_glucose,
        'Initial Glucose (mg/dL)': initial_glucose * MMOL_TO_MGDL if pd.notna(initial_glucose) else None,
        'Peak (mmol/L)': peak,
        'Peak (mg/dL)': peak * MMOL_TO_MGDL if pd.notna(peak) else None,
        'Postprandial (mmol/L)': postprandial,
        'Postprandial (mg/dL)': postprandial * MMOL_TO_MGDL if pd.notna(postprandial) else None,
        'Delta (mmol/L)': delta,
        'Delta (mg/dL)': delta * MMOL_TO_MGDL if pd.notna(delta) else None
    }

def parse_glucose_data(file_path):
    """Parse glucose data from CSV file and return processed results."""
    # Read the CSV file, skipping the first row which contains metadata
    df = pd.read_csv(file_path, skiprows=1)
    
    # Convert timestamp column to datetime
    df['Device Timestamp'] = pd.to_datetime(df['Device Timestamp'], format='%d-%m-%Y %H:%M')

    # Create a new column for glucose that prefers Scan over Historic
    df['Glucose'] = df['Scan Glucose mmol/L'].fillna(df['Historic Glucose mmol/L'])
    
    # Filter for rows with Notes
    notes_df = df[df['Notes'].notna()].copy()
    
    # Combine notes within 30-minute windows
    notes_df = combine_notes_within_window(notes_df)
    
    # Calculate average fasting glucose
    avg_fasting = calculate_fasting_glucose(df, notes_df)
    
    # Calculate average overnight glucose
    avg_overnight = calculate_overnight_glucose(df)
    
    # Process each meal/note entry
    results = []
    for _, note_row in notes_df.iterrows():
        meal_data = process_meal_data(df, note_row)
        if meal_data:
            results.append(meal_data)
    
    # Convert results to DataFrame and sort by timestamp
    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values('Timestamp')
    
    return result_df, avg_fasting, avg_overnight

def print_meal_data(row):
    """Print formatted meal data to console."""
    print(f"Time: {row['Timestamp'].strftime('%Y-%m-%d %H:%M')}")
    print(f"Note: {row['Note']}")
    print(f"Initial Glucose: {row['Initial Glucose (mmol/L)']:.1f} mmol/L ({row['Initial Glucose (mg/dL)']:.0f} mg/dL)")
    
    # Format peak value with highlight if > 7.8
    # Reference: https://en.wikipedia.org/wiki/Postprandial_glucose_test
    peak_str = f"{row['Peak (mmol/L)']:.1f} mmol/L ({row['Peak (mg/dL)']:.0f} mg/dL) ***" if pd.notna(row['Peak (mmol/L)']) and row['Peak (mmol/L)'] > 7.8 else \
              f"{row['Peak (mmol/L)']:.1f} mmol/L ({row['Peak (mg/dL)']:.0f} mg/dL)" if pd.notna(row['Peak (mmol/L)']) else "Peak (2h): N/A"
    print(f"Peak (2h): {peak_str}")
    
    # Format postprandial value with highlight if > 7.8
    postprandial_str = f"{row['Postprandial (mmol/L)']:.1f} mmol/L ({row['Postprandial (mg/dL)']:.0f} mg/dL) ***" if pd.notna(row['Postprandial (mmol/L)']) and row['Postprandial (mmol/L)'] > 7.8 else \
                     f"{row['Postprandial (mmol/L)']:.1f} mmol/L ({row['Postprandial (mg/dL)']:.0f} mg/dL)" if pd.notna(row['Postprandial (mmol/L)']) else "Postprandial (2h): N/A"
    print(f"Postprandial (2h): {postprandial_str}")
    
    delta_str = f"{row['Delta (mmol/L)']:+.1f} mmol/L ({row['Delta (mg/dL)']:+.0f} mg/dL)" if pd.notna(row['Delta (mmol/L)']) else "Delta: N/A"
    print(f"Delta: {delta_str}")
    print("-" * 50)

def print_summary_stats(result_df, avg_fasting, avg_overnight):
    """Print summary statistics to console."""
    print("\nSUMMARY STATISTICS")
    print("=" * 50)
    
    # Calculate averages, excluding NaN values
    avg_peak = result_df['Peak (mmol/L)'].mean()
    avg_postprandial = result_df['Postprandial (mmol/L)'].mean()
    
    fasting_str = f"{avg_fasting:.1f} mmol/L ({avg_fasting * MMOL_TO_MGDL:.0f} mg/dL)" if pd.notna(avg_fasting) else "Average Fasting Glucose: N/A"
    overnight_str = f"{avg_overnight:.1f} mmol/L ({avg_overnight * MMOL_TO_MGDL:.0f} mg/dL)" if pd.notna(avg_overnight) else "Average Overnight Glucose: N/A"
    
    print(f"Average Fasting Glucose: {fasting_str}")
    print(f"Average Overnight Glucose: {overnight_str}")
    print(f"Average Peak Glucose: {avg_peak:.1f} mmol/L ({avg_peak * MMOL_TO_MGDL:.0f} mg/dL)")
    print(f"Average Postprandial Glucose: {avg_postprandial:.1f} mmol/L ({avg_postprandial * MMOL_TO_MGDL:.0f} mg/dL)")
    print("=" * 50)
    
    return avg_peak, avg_postprandial

def save_csv_output(result_df, avg_fasting, avg_overnight, avg_peak, avg_postprandial, csv_file):
    """Save results to CSV file."""
    # Create output directory if it doesn't exist
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    # Prepare DataFrame for CSV output
    csv_df = result_df.copy()
    csv_df['Timestamp'] = csv_df['Timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    
    # Add summary statistics as a footer
    summary_df = pd.DataFrame([{
        'Timestamp': '',
        'Note': 'SUMMARY STATISTICS',
        'Initial Glucose (mmol/L)': avg_fasting,
        'Initial Glucose (mg/dL)': avg_fasting * MMOL_TO_MGDL if pd.notna(avg_fasting) else None,
        'Overnight Glucose (mmol/L)': avg_overnight,
        'Overnight Glucose (mg/dL)': avg_overnight * MMOL_TO_MGDL if pd.notna(avg_overnight) else None,
        'Peak (mmol/L)': avg_peak,
        'Peak (mg/dL)': avg_peak * MMOL_TO_MGDL if pd.notna(avg_peak) else None,
        'Postprandial (mmol/L)': avg_postprandial,
        'Postprandial (mg/dL)': avg_postprandial * MMOL_TO_MGDL if pd.notna(avg_postprandial) else None,
        'Delta (mmol/L)': '',
        'Delta (mg/dL)': ''
    }])
    
    # Combine meal data and summary
    csv_df = pd.concat([csv_df, summary_df], ignore_index=True)
    
    # Save to CSV
    output_file = output_dir / f"{csv_file.stem}_analysis.csv"
    csv_df.to_csv(output_file, index=False)
    print(f"\nCSV output saved to: {output_file}")

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process glucose data and generate reports')
    parser.add_argument('--csv', action='store_true', help='Generate CSV output of meal data')
    args = parser.parse_args()
    
    # Get the data directory
    data_dir = Path('data')
    
    # Process all CSV files in the data directory
    for csv_file in data_dir.glob('*.csv'):
        try:
            result_df, avg_fasting, avg_overnight = parse_glucose_data(csv_file)
            
            # Print meal data
            for _, row in result_df.iterrows():
                print_meal_data(row)
            
            # Print and get summary statistics
            avg_peak, avg_postprandial = print_summary_stats(result_df, avg_fasting, avg_overnight)
            
            # Generate CSV output if requested
            if args.csv:
                save_csv_output(result_df, avg_fasting, avg_overnight, avg_peak, avg_postprandial, csv_file)
                
        except Exception as e:
            print(f"Error processing {csv_file.name}: {str(e)}")

if __name__ == "__main__":
    main()