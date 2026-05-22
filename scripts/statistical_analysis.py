import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import scipy.stats as stats
from statsmodels.tsa.stattools import adfuller # type: ignore
from data.storage import DataStorage
from monitoring.logger import setup_logging

def main():
    logger = setup_logging()
    logger.info("Starting Statistical Return Analysis...")

    storage = DataStorage()
    
    # We load a good chunk of data to have statistical significance
    df = storage.load_rates('BTCUSD', 1, limit=50000)
    
    if df.empty:
        logger.error("No data found in local storage for BTCUSD. Run the harvester first.")
        return

    # Sort chronologically (oldest to newest) for time series analysis
    df = df.sort_values('time').reset_index(drop=True)
    logger.info(f"Loaded {len(df)} M1 bars for analysis.")

    # 1. Return Transformation
    # Percentage Returns
    df['pct_return'] = df['close'].pct_change()
    
    # Logarithmic Returns: log(P_t / P_{t-1})
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    
    # Drop the first row which will have NaN returns
    df = df.dropna().copy()
    
    returns = df['log_return'].values

    # 2. Distribution Fitting & Kurtosis
    logger.info("--- Distribution Analysis ---")
    
    # Fit normal distribution
    mu, std = stats.norm.fit(returns)
    logger.info(f"Fitted Normal Distribution: Mean (mu) = {mu:.6f}, Std Dev (sigma) = {std:.6f}")
    
    # Calculate Skewness and Kurtosis
    # Fisher's definition of kurtosis sets normal distribution kurtosis to 0.0
    skewness = stats.skew(returns)
    kurt = stats.kurtosis(returns, fisher=True) 
    
    logger.info(f"Skewness: {skewness:.4f} (0 is perfectly symmetrical)")
    logger.info(f"Excess Kurtosis: {kurt:.4f} (>0 indicates fat tails)")
    
    if kurt > 1.0:
        logger.info("Conclusion: Strong presence of 'fat tails'. Extreme price moves happen more often than a normal distribution predicts.")
    
    # 3. Stationarity Testing (Augmented Dickey-Fuller Test)
    logger.info("--- Stationarity Testing (ADF Test) ---")
    
    # Test on Raw Prices
    adf_price = adfuller(df['close'].values)
    logger.info(f"ADF Test on Raw Prices -> ADF Statistic: {adf_price[0]:.4f}, p-value: {adf_price[1]:.4f}")
    if adf_price[1] < 0.05:
        logger.info("  Result: Raw Prices ARE stationary (Reject H0).")
    else:
        logger.info("  Result: Raw Prices are NON-stationary (Fail to reject H0). This is typical for asset prices.")

    # Test on Log Returns
    adf_returns = adfuller(returns)
    logger.info(f"ADF Test on Log Returns -> ADF Statistic: {adf_returns[0]:.4f}, p-value: {adf_returns[1]:.4f}")
    if adf_returns[1] < 0.05:
        logger.info("  Result: Log Returns ARE stationary (Reject H0). They are suitable for time-series forecasting.")
    else:
        logger.info("  Result: Log Returns are NON-stationary (Fail to reject H0).")

if __name__ == "__main__":
    main()
