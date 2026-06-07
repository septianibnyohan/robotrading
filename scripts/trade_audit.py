import sys
import os
import pandas as pd
import numpy as np
import vectorbt as vbt

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from strategies.vbt_strategy import VBTsmaMomentum
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def main():
    logger = setup_logging()
    logger.info("Starting Trade-Level Auditing (Days 129-131)...")

    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDc')
    
    storage = DataStorage()
    df = storage.load_rates(symbol, 1, limit=10000)
    
    if df.empty:
        logger.error("No data found. Please ensure database has data.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    
    # 1. Run Strategy Backtest
    strategy = VBTsmaMomentum(fast_window=10, slow_window=50, rsi_window=14)
    portfolio = strategy.backtest(
        df['close'], 
        open_price=df['open'],
        init_cash=10000,
        fees=0.0006,
        freq='1m'
    )
    
    # 2. Inspect Trade Records
    trades = portfolio.trades
    trade_records = trades.records
    
    print("\n" + "="*60)
    print("           TRADE-LEVEL AUDIT REPORT")
    print("="*60)
    print(f"Total Trades: {len(trade_records)}")
    
    if len(trade_records) == 0:
        print("No trades executed. Increase data lookback or check signals.")
        return

    # 3. Analyze Individual Trade Performance
    print("\nTop 5 Most Profitable Trades:")
    print(trade_records.sort_values('pnl', ascending=False).head())
    
    print("\nTop 5 Largest Losing Trades:")
    print(trade_records.sort_values('pnl', ascending=True).head())

    # 4. Edge Ratio Analysis
    # Edge = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
    # This is essentially Expectancy.
    stats = portfolio.stats()
    win_rate = stats['Win Rate [%]'] / 100
    avg_win = stats['Avg Winning Trade [%]'] / 100
    avg_loss = abs(stats['Avg Losing Trade [%]'] / 100)
    
    edge = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    edge_ratio = (win_rate * avg_win) / ((1 - win_rate) * avg_loss) if avg_loss != 0 else np.inf

    print("\n" + "-"*60)
    print("                EDGE ANALYSIS")
    print("-"*60)
    print(f"Win Rate:               {win_rate*100:.2f}%")
    print(f"Avg Win / Avg Loss:     {avg_win/avg_loss:.2f}" if avg_loss != 0 else "Avg Win / Avg Loss: N/A")
    print(f"Expectancy (Edge):      {edge*100:.4f}% per trade")
    print(f"Edge Ratio (PF):        {edge_ratio:.4f}")
    
    # 5. Baseline Comparison (Random Entry)
    # We generate random entries with the same density as our signals
    entries, _ = strategy.run(df['close'])
    signal_density = entries.sum() / len(entries)
    random_entries = pd.Series(np.random.random(len(df)) < signal_density, index=df.index)
    # Random exit after a fixed period (e.g. 60 minutes) or just random
    random_exits = random_entries.shift(60).fillna(False)
    
    random_portfolio = vbt.Portfolio.from_signals(
        df['close'], 
        random_entries, 
        random_exits, 
        init_cash=10000, 
        fees=0.0006, 
        freq='1m'
    )
    
    random_stats = random_portfolio.stats()
    random_edge = (random_stats['Win Rate [%]']/100 * random_stats['Avg Winning Trade [%]']/100) - \
                  ((1 - random_stats['Win Rate [%]']/100) * abs(random_stats['Avg Losing Trade [%]']/100))
    
    print("\n" + "-"*60)
    print("           BASELINE COMPARISON (Random Entry)")
    print("-"*60)
    print(f"Strategy Edge:          {edge*100:.4f}%")
    print(f"Random Edge:            {random_edge*100:.4f}%")
    print(f"Net Advantage:          {(edge - random_edge)*100:.4f}%")
    
    if edge > random_edge:
        print("\nRESULT: Strategy provides a POSITIVE EDGE over random entry.")
    else:
        print("\nRESULT: Strategy currently provides NO EDGE or NEGATIVE EDGE.")
    print("="*60)

if __name__ == "__main__":
    main()
