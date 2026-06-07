import sys
import os
import pandas as pd
import optuna
import vectorbt as vbt
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from strategies.vbt_strategy import VBTsmaMomentum
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def get_data():
    storage = DataStorage()
    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDc')
    
    # Load ~50,000 bars
    df = storage.load_rates(symbol, 1, limit=50000)
    if df.empty:
        return pd.Series(), pd.Series()
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    return df['close'], df['open']

def create_objective(close, open_price):
    def objective(trial):
        fast_window = trial.suggest_int("fast_window", 15, 100)
        slow_window = trial.suggest_int("slow_window", fast_window + 10, 300)
        rsi_window = trial.suggest_int("rsi_window", 7, 28)
        
        strategy = VBTsmaMomentum(
            fast_window=fast_window, 
            slow_window=slow_window, 
            rsi_window=rsi_window
        )
        
        portfolio = strategy.backtest(
            close, 
            open_price=open_price,
            init_cash=10000,
            fees=0.0006,
            slippage=0.0001,
            tp_stop=0.002,
            freq='1m'
        )
        
        return portfolio.total_return()
        
    return objective

def main():
    logger = setup_logging()
    logger.info("Starting Walk-Forward Optimization (WFO)...")
    
    close_series, open_series = get_data()
    if close_series.empty:
        logger.error("No data available in SQLite database.")
        return
        
    # Configuration
    IS_LENGTH = 5000  # In-Sample bars
    OOS_LENGTH = 1000   # Out-Of-Sample bars
    N_TRIALS = 25       # Optuna trials per window
    
    total_bars = len(close_series)
    logger.info(f"Dataset Size: {total_bars} bars")
    logger.info(f"Configuration -> IS: {IS_LENGTH}, OOS: {OOS_LENGTH}, Step: {OOS_LENGTH}")
    
    if total_bars < IS_LENGTH + OOS_LENGTH:
        logger.error("Not enough data to form even one complete WFO window.")
        return

    # To suppress Optuna's per-trial logging to keep output clean
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    results = []
    start_idx = 0
    window_num = 1
    
    # WFO Loop
    while start_idx + IS_LENGTH + OOS_LENGTH <= total_bars:
        logger.info(f"\n--- Processing Window {window_num} ---")
        
        # 1. Slice the Data
        is_close = close_series.iloc[start_idx : start_idx + IS_LENGTH]
        is_open = open_series.iloc[start_idx : start_idx + IS_LENGTH]
        
        oos_close = close_series.iloc[start_idx + IS_LENGTH : start_idx + IS_LENGTH + OOS_LENGTH]
        oos_open = open_series.iloc[start_idx + IS_LENGTH : start_idx + IS_LENGTH + OOS_LENGTH]
        
        logger.info(f"IS Period:  {is_close.index[0]} to {is_close.index[-1]}")
        logger.info(f"OOS Period: {oos_close.index[0]} to {oos_close.index[-1]}")
        
        # 2. Optimize on In-Sample Data
        logger.info(f"Running GA Optimization ({N_TRIALS} trials)...")
        sampler = optuna.samplers.NSGAIISampler(population_size=10, mutation_prob=0.1, crossover_prob=0.9)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(create_objective(is_close, is_open), n_trials=N_TRIALS, show_progress_bar=False)
        
        best_params = study.best_params
        logger.info(f"Winning IS Genes: {best_params} (IS Return: {study.best_value*100:.2f}%)")
        
        # 3. Test on Out-Of-Sample Data
        logger.info("Executing Winning Genes on OOS data...")
        strategy = VBTsmaMomentum(**best_params)
        portfolio = strategy.backtest(
            oos_close, 
            open_price=oos_open,
            init_cash=10000,
            fees=0.0006,
            slippage=0.0001,
            tp_stop=0.002,
            freq='1m'
        )
        
        oos_stats = portfolio.stats()
        oos_return = oos_stats.get('Total Return [%]', 0.0)
        oos_trades = oos_stats.get('Total Trades', 0)
        
        logger.info(f"OOS Return: {oos_return:.2f}% | Trades: {oos_trades}")
        
        # Record Results
        is_return_decimal = study.best_value
        oos_return_decimal = oos_return / 100.0
        
        # Calculate Annualized Returns (assuming 1-minute bars)
        MINUTES_IN_YEAR = 525600
        is_ann_return = ((1 + is_return_decimal) ** (MINUTES_IN_YEAR / IS_LENGTH)) - 1
        oos_ann_return = ((1 + oos_return_decimal) ** (MINUTES_IN_YEAR / OOS_LENGTH)) - 1
        
        # Calculate Walk-Forward Efficiency (WFE)
        # Ratio of OOS annualized return to IS annualized return
        wfe = oos_ann_return / is_ann_return if is_ann_return > 0 else 0.0
        
        results.append({
            'Window': window_num,
            'IS_Start': is_close.index[0],
            'IS_End': is_close.index[-1],
            'OOS_Start': oos_close.index[0],
            'OOS_End': oos_close.index[-1],
            'Best_Params': best_params,
            'IS_Return': is_return_decimal * 100,
            'OOS_Return': oos_return,
            'IS_Ann_Return': is_ann_return * 100,
            'OOS_Ann_Return': oos_ann_return * 100,
            'WFE': wfe,
            'OOS_Trades': oos_trades
        })
        
        # 4. Slide window forward
        start_idx += OOS_LENGTH
        window_num += 1

    # Aggregated Reporting
    print("\n" + "="*80)
    print("      WALK-FORWARD OPTIMIZATION AGGREGATED REPORT")
    print("="*80)
    
    df_res = pd.DataFrame(results)
    
    avg_is_return = df_res['IS_Return'].mean()
    avg_oos_return = df_res['OOS_Return'].mean()
    total_oos_return = ( (1 + df_res['OOS_Return']/100).prod() - 1 ) * 100
    total_trades = df_res['OOS_Trades'].sum()
    
    print(f"Total Windows Evaluated: {len(results)}")
    print(f"Average IS Return per Window:  {avg_is_return:.2f}%")
    print(f"Average OOS Return per Window: {avg_oos_return:.2f}%")
    print(f"Total OOS Return (Compounded): {total_oos_return:.2f}%")
    print(f"Total OOS Trades:              {total_trades}")
    print("-" * 80)
    
    print("Window Breakdown:")
    for _, row in df_res.iterrows():
        wfe = row['WFE']
        status = "ROBUST" if wfe > 0.5 else "FRAGILE"
        print(f"Window {row['Window']}: IS Ann = {row['IS_Ann_Return']:>8.2f}% | OOS Ann = {row['OOS_Ann_Return']:>8.2f}% | WFE = {wfe:>5.2f} ({status}) | Genes: {row['Best_Params']}")
        
    print("="*80)
    logger.info("Walk-Forward Optimization finished.")

if __name__ == "__main__":
    main()
