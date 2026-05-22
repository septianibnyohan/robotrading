import sys
import os
import json
import pandas as pd
import vectorbt as vbt

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from strategies.vbt_strategy import VBTsmaMomentum
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def load_best_params(logger):
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "best_strategy_params.json")
    if not os.path.exists(config_path):
        logger.error(f"Parameter file not found: {config_path}")
        return None
        
    with open(config_path, "r") as f:
        data = json.load(f)
    
    return data.get("parameters", None)

def main():
    logger = setup_logging()
    logger.info("Starting Out-Of-Sample (OOS) Validation...")
    
    # 1. Load Parameters
    best_params = load_best_params(logger)
    if not best_params:
        logger.error("Could not load best parameters. Exiting.")
        return
        
    logger.info(f"Loaded Winning Genes: {best_params}")
    
    # 2. Fetch Data
    storage = DataStorage()
    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDm')
    
    # Load 60,000 bars for split (approx 40 days)
    df = storage.load_rates(symbol, 1, limit=60000)
    if df.empty:
        logger.error("No data available.")
        return
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    
    # 3. Data Segmentation (80% IS / 20% OOS)
    split_idx = int(len(df) * 0.8)
    
    df_is = df.iloc[:split_idx]
    df_oos = df.iloc[split_idx:]
    
    logger.info(f"In-Sample (Train) Period: {df_is.index[0]} to {df_is.index[-1]} ({len(df_is)} bars)")
    logger.info(f"Out-of-Sample (Test) Period: {df_oos.index[0]} to {df_oos.index[-1]} ({len(df_oos)} bars)")
    
    # 4. Instantiate Strategy
    strategy = VBTsmaMomentum(**best_params)
    
    # 5. Run IS Backtest
    logger.info("Running backtest on In-Sample data...")
    pf_is = strategy.backtest(
        df_is['close'], 
        open_price=df_is['open'],
        init_cash=10000,
        fees=0.0006,
        slippage=0.0001,
        tp_stop=0.002,
        freq='1m'
    )
    stats_is = pf_is.stats()
    
    # 6. Run OOS Backtest
    logger.info("Running backtest on Out-Of-Sample data...")
    pf_oos = strategy.backtest(
        df_oos['close'], 
        open_price=df_oos['open'],
        init_cash=10000,
        fees=0.0006,
        slippage=0.0001,
        tp_stop=0.002,
        freq='1m'
    )
    stats_oos = pf_oos.stats()
    
    # 7. Comparative Output
    print("\n" + "="*60)
    print("      OUT-OF-SAMPLE VALIDATION REPORT")
    print("="*60)
    
    metrics = ["Total Return [%]", "Win Rate [%]", "Max Drawdown [%]", "Sharpe Ratio", "Profit Factor", "Total Trades"]
    
    print(f"{'Metric':<25} | {'In-Sample (Train)':<15} | {'Out-of-Sample (Test)':<15}")
    print("-" * 60)
    
    for m in metrics:
        val_is = stats_is.get(m, 0.0)
        val_oos = stats_oos.get(m, 0.0)
        
        # Formatting
        if "Ratio" in m or "Factor" in m:
            str_is = f"{val_is:.4f}"
            str_oos = f"{val_oos:.4f}"
        elif "Trades" in m:
            str_is = f"{val_is}"
            str_oos = f"{val_oos}"
        else:
            str_is = f"{val_is:.2f}%"
            str_oos = f"{val_oos:.2f}%"
            
        print(f"{m:<25} | {str_is:<15} | {str_oos:<15}")
        
    print("="*60)
    
    # Analyze Curve Fitting
    return_is = stats_is.get("Total Return [%]", 0)
    return_oos = stats_oos.get("Total Return [%]", 0)
    
    if return_is > 0 and return_oos < 0:
        logger.warning("CRITICAL STRATEGY DECAY DETECTED! Strategy is profitable In-Sample but loses money Out-of-Sample.")
        logger.warning("Conclusion: The parameters are heavily curve-fitted to historical noise and will likely fail in live trading.")
    elif return_is < 0 and return_oos < 0:
        logger.info("Strategy is unprofitable in both periods.")
    else:
        logger.info("Strategy performance holds up across segmentation. Robustness confirmed.")
        
if __name__ == "__main__":
    main()
