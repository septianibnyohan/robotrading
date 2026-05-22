import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.storage import DataStorage
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    logger.info("Starting Spread Stability Analysis...")

    storage = DataStorage()
    # Load a significant amount of data for statistical significance
    df = storage.load_rates('BTCUSD', 1, limit=200000)
    
    if df.empty:
        logger.error("No data found in database.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    logger.info(f"Loaded {len(df)} M1 bars for analysis.")

    # --- 1. Global Spread Statistics ---
    min_spread = df['spread'].min()
    logger.info(f"Absolute Minimum Spread found: {min_spread}")
    
    # Exness claims 99.98% stability at "minimum levels". 
    # Usually "minimum levels" refers to the typical tight spread (e.g. 0-200 points)
    # Let's see the distribution
    spread_counts = df['spread'].value_counts(normalize=True).sort_index()
    cumulative_stability = spread_counts.cumsum()
    
    # Let's find the spread value where 99.98% of data falls under
    p9998 = df['spread'].quantile(0.9998)
    logger.info(f"99.98th percentile spread: {p9998}")
    
    # If the claim is that it's at the ABSOLUTE minimum 99.98% of the time:
    min_stability = (df['spread'] == min_spread).mean() * 100
    logger.info(f"Percentage of time at absolute minimum ({min_spread}): {min_stability:.4f}%")

    # --- 2. News Spike Analysis ---
    try:
        from openbb import obb
        date_from = df['time'].min().strftime('%Y-%m-%d')
        date_to = df['time'].max().strftime('%Y-%m-%d')
        logger.info(f"Fetching OpenBB calendar events from {date_from} to {date_to}...")

        calendar_data = obb.economy.calendar(start_date=date_from, end_date=date_to, provider="nasdaq")
        cal_df = calendar_data.to_df()
        
        if not cal_df.empty:
            cal_df = cal_df.reset_index()
            cal_df['date'] = pd.to_datetime(cal_df['date'])
            if cal_df['date'].dt.tz is None:
                cal_df['date'] = cal_df['date'].dt.tz_localize('UTC')
            else:
                cal_df['date'] = cal_df['date'].dt.tz_convert('UTC')
            
            # Filter for high-impact US events (approximated by country)
            high_impact = cal_df[cal_df['country'] == 'United States'].copy()
            event_timestamps = high_impact['date'].tolist()
            logger.info(f"Found {len(event_timestamps)} US events.")
        else:
            event_timestamps = []
    except Exception as e:
        logger.error(f"Failed to fetch calendar data: {e}")
        event_timestamps = []

    if event_timestamps:
        spike_spreads = []
        for T in event_timestamps:
            # Define "spike window" as -5 to +15 minutes
            window_start = T - timedelta(minutes=5)
            window_end = T + timedelta(minutes=15)
            mask = (df['time'] >= window_start) & (df['time'] <= window_end)
            spike_df = df.loc[mask]
            if not spike_df.empty:
                spike_spreads.append(spike_df['spread'])
        
        if spike_spreads:
            all_spike_spreads = pd.concat(spike_spreads)
            avg_spike_spread = all_spike_spreads.mean()
            max_spike_spread = all_spike_spreads.max()
            logger.info(f"Average spread during news spikes: {avg_spike_spread:.2f}")
            logger.info(f"Max spread during news spikes: {max_spike_spread:.2f}")
            
            # Slippage Buffer Calculation
            # Buffer = Max Spread during news - Typical Spread
            typical_spread = df['spread'].median()
            slippage_buffer = max_spike_spread - typical_spread
            logger.info(f"Recommended Slippage Buffer: {slippage_buffer:.2f} points")
        else:
            logger.warning("No data points found during news windows.")
    else:
        logger.warning("No events to analyze for spikes.")

    # --- 3. Visualization ---
    plt.figure(figsize=(10, 6))
    plt.hist(df['spread'], bins=100, alpha=0.7, label='Full Data Distribution', color='blue')
    plt.axvline(p9998, color='red', linestyle='--', label=f'99.98th Percentile ({p9998})')
    plt.title('BTCUSD Spread Distribution & Stability Analysis')
    plt.xlabel('Spread (Points)')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'spread_analysis.png')
    plt.savefig(plot_path)
    logger.info(f"Chart saved to {plot_path}")

if __name__ == "__main__":
    main()
