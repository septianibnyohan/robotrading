import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import matplotlib.pyplot as plt
from data.storage import DataStorage
from utils.volatility import parkinson_estimator
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    logger.info("Starting Volatility Analysis (Parkinson Estimator)...")

    storage = DataStorage()
    
    # Load raw M1 data
    df_m1 = storage.load_rates('BTCUSD', 1, limit=100000)
    
    if df_m1.empty:
        logger.error("No data found for BTCUSD. Please run the harvester to gather data.")
        return
        
    df_m1 = df_m1.sort_values('time').reset_index(drop=True)
    logger.info(f"Loaded {len(df_m1)} M1 bars.")

    # 1. Resample to M5
    # Ensure time is datetime and set as index for resampling
    df_m1['time'] = pd.to_datetime(df_m1['time'])
    df_m5 = df_m1.resample('5min', on='time').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).dropna().reset_index()
    
    logger.info(f"Resampled to {len(df_m5)} M5 bars.")
    
    # 2. Real-time Monitoring Simulation: Calculate Rolling Parkinson Volatility (14-period on M5)
    # This is equivalent to a 70-minute rolling window
    df_m5['parkinson_vol_14'] = parkinson_estimator(df_m5['high'], df_m5['low'], window=14)
    
    # Drop rows where the rolling calculation is NaN (first 13 rows)
    df_m5_clean = df_m5.dropna(subset=['parkinson_vol_14']).copy()
    
    if df_m5_clean.empty:
        logger.warning(f"Not enough data to compute a {14}-period rolling window on M5 data. Only {len(df_m5)} bars available.")
        return
        
    # Show the latest volatility clusters
    logger.info("Latest M5 Volatility Readings:")
    logger.info(f"\n{df_m5_clean[['time', 'close', 'parkinson_vol_14']].tail()}")

    # 3. Intraday Seasonality Analysis
    # Extract the hour (UTC)
    df_m5_clean['hour_utc'] = df_m5_clean['time'].dt.hour
    
    # Group by hour and calculate mean volatility
    hourly_vol = df_m5_clean.groupby('hour_utc')['parkinson_vol_14'].mean().reset_index()
    
    logger.info("Intraday Seasonality (Mean Parkinson Volatility by UTC Hour):")
    for _, row in hourly_vol.iterrows():
        # Format for nice console output
        logger.info(f"Hour {int(row['hour_utc']):02d}:00 UTC -> Volatility: {row['parkinson_vol_14']:.6f}")
        
    # Find the most and least volatile hours
    peak_hour = hourly_vol.loc[hourly_vol['parkinson_vol_14'].idxmax()]
    quiet_hour = hourly_vol.loc[hourly_vol['parkinson_vol_14'].idxmin()]
    
    logger.info(f"Peak Volatility Hour: {int(peak_hour['hour_utc']):02d}:00 UTC")
    logger.info(f"Quiet Volatility Hour: {int(quiet_hour['hour_utc']):02d}:00 UTC")

    # Generate a simple plot
    try:
        plt.figure(figsize=(10, 5))
        plt.plot(hourly_vol['hour_utc'], hourly_vol['parkinson_vol_14'], marker='o', linestyle='-', color='b')
        plt.title('Intraday Seasonality: Average M5 Parkinson Volatility by UTC Hour')
        plt.xlabel('Hour of Day (UTC)')
        plt.ylabel('Average Parkinson Volatility')
        plt.xticks(range(0, 24))
        plt.grid(True, alpha=0.3)
        
        plot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'volatility_seasonality.png')
        plt.savefig(plot_path)
        logger.info(f"Saved seasonality plot to {plot_path}")
    except Exception as e:
        logger.error(f"Failed to generate plot: {e}")

if __name__ == "__main__":
    main()
