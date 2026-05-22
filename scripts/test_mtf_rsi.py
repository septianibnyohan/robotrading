import sys
import os
import MetaTrader5 as mt5

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mt5_bridge import MT5Bridge
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials
from data.storage import DataStorage
from data.harvester import DataHarvester
from strategies.mtf_rsi import MultiTimeframeRSIStrategy

def main():
    logger = setup_logging()
    
    bridge = MT5Bridge()
    if not bridge.connect():
        logger.error("Failed to connect to MT5")
        return
        
    try:
        credentials = get_mt5_credentials()
        symbol = credentials.get('symbol', 'BTCUSD')
        logger.info(f"Connected successfully to MT5. Testing MTF RSI on {symbol}...")
        
        storage = DataStorage()
        harvester = DataHarvester(storage)
        strategy = MultiTimeframeRSIStrategy()
        
        timeframes = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4
        }
        
        dfs = {}
        for tf_name, tf_const in timeframes.items():
            logger.info(f"Fetching data for {tf_name}...")
            df = harvester.fetch_ohlcv(symbol, tf_const, count=250)
            if df.empty:
                logger.error(f"Failed to fetch data for {tf_name}")
                return
            logger.info(f"Successfully fetched {len(df)} candles for {tf_name}.")
            dfs[tf_name] = df
            
        logger.info("Executing MultiTimeframeRSIStrategy.generate_signals...")
        df_signals = strategy.generate_signals(dfs)
        
        if df_signals.empty:
            logger.error("Strategy returned empty signals DataFrame.")
            return
            
        logger.info(f"Signals DataFrame shape: {df_signals.shape}")
        
        # Display the last few rows to inspect aligned values and signals
        cols_to_print = [
            'time', 'close', 'rsi_M1', 'rsi_M5', 'rsi_M15', 
            'rsi_M30', 'rsi_H1', 'rsi_H4', 
            'bull_trend', 'bear_trend', 'buy_setup', 'sell_setup',
            'long_entry', 'short_entry', 'long_exit', 'short_exit'
        ]
        
        available_cols = [c for c in cols_to_print if c in df_signals.columns]
        logger.info("Last 5 rows of aligned MTF DataFrame:")
        print(df_signals[available_cols].tail(5).to_string())
        
    finally:
        bridge.disconnect()
        logger.info("Disconnected from MT5.")

if __name__ == "__main__":
    main()
