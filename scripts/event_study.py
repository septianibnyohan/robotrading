import sys
import os
import random
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.storage import DataStorage
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    logger.info("Starting Event Window Analysis...")

    storage = DataStorage()
    df = storage.load_rates('BTCUSD', 1, limit=100000)
    
    if df.empty or len(df) < 130:
        logger.error("Not enough data to perform event analysis. We need at least 130 M1 bars.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    logger.info(f"Loaded {len(df)} M1 bars for analysis.")

    # 1. Event Ingestion (OpenBB Economic Calendar)
    try:
        from openbb import obb
        
        # Define time range based on available price data
        date_from = df['time'].min().strftime('%Y-%m-%d')
        date_to = df['time'].max().strftime('%Y-%m-%d')
        logger.info(f"Fetching OpenBB calendar events from {date_from} to {date_to}...")

        # Using 'nasdaq' as it usually doesn't require an API key
        # Note: OpenBB might take a moment to initialize extensions on first run
        calendar_data = obb.economy.calendar(start_date=date_from, end_date=date_to, provider="nasdaq")
        cal_df = calendar_data.to_df()
        
        if not cal_df.empty:
            # OpenBB returns data with a DatetimeIndex
            cal_df = cal_df.reset_index()
            cal_df['date'] = pd.to_datetime(cal_df['date'])
            
            # Ensure UTC localization to match price data (aware vs naive comparison fix)
            if cal_df['date'].dt.tz is None:
                cal_df['date'] = cal_df['date'].dt.tz_localize('UTC')
            else:
                cal_df['date'] = cal_df['date'].dt.tz_convert('UTC')
            
            # Since 'nasdaq' doesn't provide 'importance', we filter for US events
            # as they are usually the most relevant for BTCUSD movements.
            high_impact = cal_df[cal_df['country'] == 'United States'].copy()
            
            # Only keep events that are within the price data range with 60min buffer
            price_start = df['time'].min() + timedelta(minutes=60)
            price_end = df['time'].max() - timedelta(minutes=60)
            
            high_impact = high_impact[(high_impact['date'] >= price_start) & (high_impact['date'] <= price_end)]
            event_timestamps = high_impact['date'].tolist()
            
            logger.info(f"Found {len(event_timestamps)} US calendar events within data range.")
        else:
            logger.warning("No calendar events found for this period.")
            event_timestamps = []

    except Exception as e:
        logger.error(f"Failed to fetch OpenBB calendar data: {e}")
        event_timestamps = []

    if not event_timestamps:
        logger.error("No events to analyze. Exiting.")
        return

    # 2. Window Extraction & Normalization
    trajectories = []
    
    for T in event_timestamps:
        window_start = T - timedelta(minutes=60)
        window_end = T + timedelta(minutes=60)
        
        # Extract the 120-minute window
        mask = (df['time'] >= window_start) & (df['time'] <= window_end)
        event_df = df.loc[mask].copy()
        
        # Ensure we have a reasonable amount of data in the window
        if len(event_df) < 100:
            continue
            
        # Calculate relative minutes [-60, +60]
        event_df['relative_minutes'] = (event_df['time'] - T).dt.total_seconds() / 60.0
        
        # Round relative minutes to nearest integer to align them perfectly
        event_df['relative_minutes'] = event_df['relative_minutes'].round().astype(int)
        
        # Find the price exactly at T=0
        t0_rows = event_df[event_df['relative_minutes'] == 0]
        if t0_rows.empty:
            continue
            
        price_at_t0 = t0_rows['close'].iloc[0]
        
        # Normalize: Calculate percentage return relative to the event time (T=0)
        event_df['normalized_return'] = (event_df['close'] / price_at_t0) - 1.0
        
        # Extract the series indexed by relative_minutes
        trajectory = event_df.set_index('relative_minutes')['normalized_return']
        trajectories.append(trajectory)
        
    if not trajectories:
        logger.error("Failed to extract valid trajectories.")
        return
        
    # 3. Aggregation
    # Combine all trajectories into a single dataframe
    all_trajectories = pd.concat(trajectories, axis=1)
    
    # Calculate the mean trajectory (average market response)
    mean_trajectory = all_trajectories.mean(axis=1)

    # 4. Visualization
    logger.info("Plotting Event Study results...")
    try:
        plt.figure(figsize=(12, 6))
        
        # Plot individual events faintly
        for col in all_trajectories.columns:
            plt.plot(all_trajectories.index, all_trajectories[col] * 100, color='gray', alpha=0.3)
            
        # Plot the mean trajectory boldly
        plt.plot(mean_trajectory.index, mean_trajectory * 100, color='blue', linewidth=2.5, label='Average Response')
        
        # Mark the Event Time
        plt.axvline(x=0, color='red', linestyle='--', label='Event Release (T=0)')
        
        # Mark the hypothesized 45-minute processing time
        plt.axvline(x=45, color='green', linestyle=':', label='Hypothesized T+45m (Stabilization)')
        plt.axhline(y=0, color='black', linewidth=1)
        
        plt.title('Event Window Analysis: BTCUSD Response to Macro News')
        plt.xlabel('Minutes Relative to Event')
        plt.ylabel('Normalized Return (%)')
        plt.legend()
        plt.grid(True, alpha=0.2)
        
        plot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'event_study.png')
        plt.savefig(plot_path)
        logger.info(f"Successfully generated Event Study chart at: {plot_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate plot: {e}")

if __name__ == "__main__":
    main()
