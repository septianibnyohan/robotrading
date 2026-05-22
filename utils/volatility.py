import numpy as np
import pandas as pd

def parkinson_estimator(high_series: pd.Series, low_series: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculates the Parkinson Volatility Estimator over a rolling window.
    
    Formula:
    sqrt( 1 / (4 * N * ln(2)) * sum( ln(H_i / L_i)^2 ) )
    
    Args:
        high_series (pd.Series): Series of high prices.
        low_series (pd.Series): Series of low prices.
        window (int): Rolling window size (N).
        
    Returns:
        pd.Series: Rolling Parkinson Volatility.
    """
    # 1. Calculate squared log ratio of high to low for each period
    log_hl_sq = np.log(high_series / low_series) ** 2
    
    # 2. Calculate the rolling mean of the squared log ratios
    # rolling.mean() effectively does the (1/N) * sum(...) part of the formula
    rolling_mean_sq = log_hl_sq.rolling(window=window).mean()
    
    # 3. Apply the scaling factor and take the square root
    scaling_factor = 1.0 / (4.0 * np.log(2.0))
    
    parkinson_vol = np.sqrt(scaling_factor * rolling_mean_sq)
    
    return parkinson_vol
