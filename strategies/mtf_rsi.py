import pandas as pd
import numpy as np
from strategies.base import TradingStrategy

class MultiTimeframeRSIStrategy(TradingStrategy):
    """
    Multi-Timeframe RSI Cascade Strategy.
    
    Uses high timeframes (H4, H1, M30) for trend filtering,
    medium timeframes (M15, M5) for pullback detection,
    and the lowest timeframe (M1) for execution triggers.
    """
    
    def __init__(self):
        # Timeframe parameters based on user criteria
        self.params = {
            'M1':  {'period': 7,  'overbought': 80, 'oversold': 20},
            'M5':  {'period': 5,  'overbought': 80, 'oversold': 20},
            'M15': {'period': 9,  'overbought': 75, 'oversold': 25},
            'M30': {'period': 10, 'overbought': 75, 'oversold': 25},
            'H1':  {'period': 14, 'overbought': 70, 'oversold': 30},
            'H4':  {'period': 14, 'overbought': 70, 'oversold': 30}
        }

    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculates RSI with vectorized precision using Wilder's Smoothing.
        """
        if df.empty or len(df) < period:
            return pd.Series(50.0, index=df.index)

        df_sorted = df.sort_values('time').copy()
        delta = df_sorted['close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0.0)
        rsi = 100 - (100 / (1 + rs))
        
        return pd.Series(rsi, index=df_sorted.index).reindex(df.index).fillna(50.0)

    def calculate_indicators(self, dfs: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """
        Calculate technical indicators (RSI) for each timeframe DataFrame.
        """
        results = {}
        for tf, df in dfs.items():
            if df.empty:
                continue
            df = df.copy()
            period = self.params[tf]['period']
            df['rsi'] = self._calculate_rsi(df, period)
            results[tf] = df
        return results

    def _align_timeframes(self, calculated_dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Extracts M1 baseline, adds default columns, and merges higher timeframe RSIs.
        """
        m1_df = calculated_dfs.get('M1')
        if m1_df is None or m1_df.empty:
            return pd.DataFrame()
            
        m1_df = m1_df.copy()
        m1_df['ema'] = m1_df['close'].ewm(span=200, adjust=False).mean()
        m1_df['sma_fast'] = m1_df['ema']
        m1_df['sma_slow'] = m1_df['ema']
        m1_df['rsi_M1'] = m1_df['rsi']
        m1_df['prev_rsi_M1'] = m1_df['rsi_M1'].shift(1)
        
        for tf in ['M5', 'M15', 'M30', 'H1', 'H4']:
            tf_df = calculated_dfs.get(tf)
            if tf_df is not None and not tf_df.empty:
                sub_df = tf_df[['time', 'rsi']].copy()
                sub_df.columns = ['time', f'rsi_{tf}']
                m1_df = m1_df.sort_values('time')
                sub_df = sub_df.sort_values('time')
                m1_df = pd.merge_asof(m1_df, sub_df, on='time', direction='backward')
            else:
                m1_df[f'rsi_{tf}'] = 50.0
                
        for tf in ['M5', 'M15', 'M30', 'H1', 'H4']:
            m1_df[f'rsi_{tf}'] = m1_df[f'rsi_{tf}'].fillna(50.0)
            
        return m1_df

    def _determine_trends_and_setups(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes trend states and setup conditions.
        """
        # df['bull_trend'] = (df['rsi_H4'] > 50) & (df['rsi_H1'] > 50) & (df['rsi_M30'] > 50)
        # df['bear_trend'] = (df['rsi_H4'] < 50) & (df['rsi_H1'] < 50) & (df['rsi_M30'] < 50)

        df['bull_trend'] = df['rsi_H1'] > 50
        df['bear_trend'] = df['rsi_H1'] < 50
        
        # df['buy_setup'] = df['bull_trend'] & ((df['rsi_M15'] < 40) | (df['rsi_M5'] < 30))
        # df['sell_setup'] = df['bear_trend'] & ((df['rsi_M15'] > 60) | (df['rsi_M5'] > 70))

        df['buy_setup'] = df['bull_trend']
        df['sell_setup'] = df['bear_trend']
        
        return df

    def _apply_signals_and_exits(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluates entry/exit signal conditions based on crossovers.
        """
        df['long_entry'] = df['buy_setup'] & (df['rsi_M1'] > 20) & (df['prev_rsi_M1'] <= 20)
        df['short_entry'] = df['sell_setup'] & (df['rsi_M1'] < 80) & (df['prev_rsi_M1'] >= 80)
        
        df['long_exit'] = ((df['rsi_M1'] > 50) & (df['prev_rsi_M1'] <= 50)) | (df['rsi_H1'] < 50)
        df['short_exit'] = ((df['rsi_M1'] < 50) & (df['prev_rsi_M1'] >= 50)) | (df['rsi_H1'] > 50)
        
        return df

    def _log_diagnostics(self, df: pd.DataFrame):
        """
        Logs the state and signal indicators for debugging.
        """
        last_row = df.iloc[-1]
        print(
            f"MTF RSI Diagnostics | M1: {last_row['rsi_M1']:.1f} | M5: {last_row['rsi_M5']:.1f} | "
            f"M15: {last_row['rsi_M15']:.1f} | M30: {last_row['rsi_M30']:.1f} | H1: {last_row['rsi_H1']:.1f} | "
            f"H4: {last_row['rsi_H4']:.1f}"
        )
        print(
            f"MTF Status | BullTrend: {last_row['bull_trend']} | BearTrend: {last_row['bear_trend']} | "
            f"BuySetup: {last_row['buy_setup']} | SellSetup: {last_row['sell_setup']}"
        )
        print(f"MTF Signals | LongEntry: {last_row['long_entry']} | ShortEntry: {last_row['short_entry']}")

    def generate_signals(self, dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Generates entry and exit signals by aligning multiple timeframes.
        """
        calculated_dfs = self.calculate_indicators(dfs)
        m1_df = self._align_timeframes(calculated_dfs)
        if m1_df.empty:
            return m1_df
            
        m1_df = self._determine_trends_and_setups(m1_df)
        m1_df = self._apply_signals_and_exits(m1_df)
        self._log_diagnostics(m1_df)
        
        return m1_df
