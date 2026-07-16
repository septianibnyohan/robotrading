import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import btc_config

def rates_to_df(rates):
    """Converts MT5 rates structure to a pandas DataFrame."""
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def fetch_rates(symbol, timeframe, count):
    """Fetches historical rates from MetaTrader 5."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    return rates_to_df(rates)

def compute_emas(df):
    """Calculates EMAs for M5 timeframe."""
    df['ema_9'] = df['close'].ewm(span=btc_config.EMA_FAST, adjust=False).mean()
    df['ema_21'] = df['close'].ewm(span=btc_config.EMA_MED, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=btc_config.EMA_SLOW, adjust=False).mean()
    return df

def compute_rsi(df, period=None):
    """Calculates RSI."""
    if period is None:
        period = btc_config.RSI_PERIOD
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0.0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 1e-10)
    df['rsi_14'] = 100 - (100 / (1 + rs))
    return df

def compute_atr(df):
    """Calculates True Range and ATR."""
    high_low = df['high'] - df['low']
    high_prev = (df['high'] - df['close'].shift(1)).abs()
    low_prev = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_prev, low_prev], axis=1).max(axis=1)
    df['atr_14'] = tr.ewm(alpha=1/btc_config.ATR_PERIOD, adjust=False).mean()
    return df, tr

def compute_adx(df, tr):
    """Calculates ADX on M5 timeframe."""
    plus_dm = df['high'].diff()
    minus_dm = -df['low'].diff()  # low.shift(1) - low
    
    plus_dm_clean = np.where((plus_dm > 0) & (plus_dm > minus_dm), plus_dm, 0.0)
    minus_dm_clean = np.where((minus_dm > 0) & (minus_dm > plus_dm), minus_dm, 0.0)
    
    tr_smoothed = tr.ewm(alpha=1/btc_config.ADX_PERIOD, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm_clean).ewm(alpha=1/btc_config.ADX_PERIOD, adjust=False).mean() / (tr_smoothed + 1e-10)
    minus_di = 100 * pd.Series(minus_dm_clean).ewm(alpha=1/btc_config.ADX_PERIOD, adjust=False).mean() / (tr_smoothed + 1e-10)
    
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    df['adx_14'] = dx.ewm(alpha=1/btc_config.ADX_PERIOD, adjust=False).mean()
    return df

def calculate_m5_indicators(df):
    """Orchestrates all M5 calculations."""
    df = df.sort_values('time').copy()
    df = compute_emas(df)
    df = compute_rsi(df)
    df, tr = compute_atr(df)
    df = compute_adx(df, tr)
    df['volume_ema_10'] = df['tick_volume'].ewm(span=btc_config.VOL_EMA_PERIOD, adjust=False).mean()
    return df

def calculate_h1_indicators(df):
    """Calculates H1 indicators (EMA 50 and slope)."""
    df = df.sort_values('time').copy()
    df['ema_50'] = df['close'].ewm(span=btc_config.H1_EMA_PERIOD, adjust=False).mean()
    df['ema_50_slope'] = df['ema_50'].diff()
    return df

def calculate_m15_indicators(df):
    """Calculates M15 indicators (EMA 200)."""
    df = df.sort_values('time').copy()
    df['ema_200'] = df['close'].ewm(span=btc_config.EMA_SLOW, adjust=False).mean()
    return df

def calculate_m1_layer_indicators(df):
    """Calculates M1 indicators (RSI 7)."""
    df = df.sort_values('time').copy()
    rsi_period = getattr(btc_config, 'RSI_PERIOD_M1', 7)
    df = compute_rsi(df, period=rsi_period)
    return df

def calculate_h1_layer_indicators(df):
    """Calculates H1 layering indicators (EMA 200, RSI 14, and ATR 14)."""
    df = df.sort_values('time').copy()
    df['ema_200'] = df['close'].ewm(span=btc_config.EMA_SLOW, adjust=False).mean()
    df = compute_rsi(df)
    df, _ = compute_atr(df)
    return df
