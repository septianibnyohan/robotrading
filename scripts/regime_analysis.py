import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.storage import DataStorage
from monitoring.logger import setup_logging

def calculate_volatility(df, window=5):
    """Calculates rolling volatility (std dev of log returns)."""
    df = df.sort_values('time').copy()
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    df['volatility'] = df['log_return'].rolling(window=window).std()
    return df[['time', 'volatility']]

def main():
    logger = setup_logging()
    logger.info("Starting Regime Correlation Analysis...")

    storage = DataStorage()
    
    # Load data
    btc_df = storage.load_rates('BTCUSD', 1, limit=10000)
    xau_df = storage.load_rates('XAUUSD', 1, limit=10000)
    nas_df = storage.load_rates('USTEC', 1, limit=10000)
    
    if btc_df.empty or xau_df.empty or nas_df.empty:
        logger.error("Missing data for one or more symbols.")
        return

    # Process Volatility
    btc_vol = calculate_volatility(btc_df)
    xau_vol = calculate_volatility(xau_df)
    nas_vol = calculate_volatility(nas_df)

    # Merge dataframes on time
    merged = pd.merge(btc_vol, xau_vol, on='time', suffixes=('_btc', '_xau'))
    merged = pd.merge(merged, nas_vol, on='time')
    merged.rename(columns={'volatility': 'volatility_nas'}, inplace=True)
    merged.dropna(inplace=True)
    
    merged['time'] = pd.to_datetime(merged['time'])

    # --- Fetch News Windows ---
    try:
        from openbb import obb
        date_from = merged['time'].min().strftime('%Y-%m-%d')
        date_to = merged['time'].max().strftime('%Y-%m-%d')
        logger.info(f"Fetching news for range: {date_from} to {date_to}")
        
        calendar_data = obb.economy.calendar(start_date=date_from, end_date=date_to, provider="nasdaq")
        cal_df = calendar_data.to_df()
        
        if not cal_df.empty:
            cal_df = cal_df.reset_index()
            cal_df['date'] = pd.to_datetime(cal_df['date'])
            if cal_df['date'].dt.tz is None:
                cal_df['date'] = cal_df['date'].dt.tz_localize('UTC')
            else:
                cal_df['date'] = cal_df['date'].dt.tz_convert('UTC')
            
            high_impact = cal_df[cal_df['country'] == 'United States'].copy()
            event_timestamps = high_impact['date'].tolist()
        else:
            event_timestamps = []
    except Exception as e:
        logger.error(f"Failed to fetch news: {e}")
        event_timestamps = []

    # Filter for News Windows (±30 minutes around event)
    news_masks = []
    for T in event_timestamps:
        window_start = T - timedelta(minutes=30)
        window_end = T + timedelta(minutes=30)
        news_masks.append((merged['time'] >= window_start) & (merged['time'] <= window_end))
    
    if news_masks:
        combined_mask = np.logical_or.reduce(news_masks)
        news_data = merged.loc[combined_mask].copy()
        logger.info(f"Analyzed {len(news_data)} minutes of news-impacted data.")
    else:
        logger.warning("No news events found in data range. Using full dataset.")
        news_data = merged.copy()

    # --- Correlation Analysis ---
    corr_matrix = news_data[['volatility_btc', 'volatility_xau', 'volatility_nas']].corr()
    logger.info("\nVolatility Correlation Matrix during News Windows:")
    logger.info(f"\n{corr_matrix}")

    # Determine Regime
    btc_nas_corr = corr_matrix.loc['volatility_btc', 'volatility_nas']
    btc_xau_corr = corr_matrix.loc['volatility_btc', 'volatility_xau']
    
    regime = "RISK-ON" if btc_nas_corr > btc_xau_corr else "SAFE-HAVEN"
    logger.info(f"Current Regime: {regime}")

    # --- Visualization ---
    plt.figure(figsize=(8, 6))
    cax = plt.imshow(corr_matrix, cmap='coolwarm', vmin=-1, vmax=1)
    plt.colorbar(cax)
    
    # Add labels
    ticks = np.arange(len(corr_matrix.columns))
    plt.xticks(ticks, corr_matrix.columns, rotation=45)
    plt.yticks(ticks, corr_matrix.columns)
    
    # Add annotations
    for i in range(len(corr_matrix.columns)):
        for j in range(len(corr_matrix.columns)):
            plt.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}', ha='center', va='center', color='black')

    plt.title(f'Volatility Correlation (Regime: {regime})\nBTC vs XAU vs USTEC (News Windows)')
    plt.tight_layout()
    
    plot_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'regime_analysis.png')
    plt.savefig(plot_path)
    logger.info(f"Correlation heatmap saved to {plot_path}")

if __name__ == "__main__":
    main()
