import sys
import os
import pandas as pd
import optuna
import vectorbt as vbt
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.storage import DataStorage
from strategies.vbt_rsi_ema_scalper import VBTrsiEmaScalper
from monitoring.logger import setup_logging
from config.credentials import get_mt5_credentials

def get_data():
    storage = DataStorage()
    credentials = get_mt5_credentials()
    symbol = credentials.get('symbol', 'BTCUSDm')
    
    # Load 50,000 bars for robust optimization
    df = storage.load_rates(symbol, 1, limit=50000)
    if df.empty:
        return pd.Series(), pd.Series()
        
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time').set_index('time')
    return df['close'], df['open']

def create_objective(close, open_price):
    """
    Creates the objective function, injecting the market data closure.
    """
    def objective(trial):
        # 1. Parameter Suggestion (The "Genes")
        ema_window = trial.suggest_int("ema_window", 50, 400)
        rsi_window = trial.suggest_int("rsi_window", 2, 14)
        rsi_extreme = trial.suggest_int("rsi_extreme", 5, 40)
        
        # 2. Instantiate Strategy with suggested genes
        strategy = VBTrsiEmaScalper(
            ema_window=ema_window, 
            rsi_window=rsi_window, 
            rsi_extreme=rsi_extreme
        )
        
        # 3. Run Simulation
        portfolio = strategy.backtest(
            close, 
            open_price=open_price,
            init_cash=10000,
            fees=0.0006,
            slippage=0.0001,
            tp_stop=0.002, # Include recent TP logic
            freq='1m'
        )
        
        # 4. Return Fitness Score
        # We maximize Total Return as requested
        return portfolio.total_return()
        
    return objective

def audit_parameter_sensitivity(best_params, base_return, close, open_price, logger):
    """
    Stress tests the best parameters by shifting them slightly.
    If performance drops catastrophically, flags the parameter set as fragile.
    """
    logger.info("Running Parameter Sensitivity Audit on Best Genes...")
    fragile = False
    max_drop = 0.0
    
    # We test shifting each parameter
    shifts = {
        "ema_window": [-10, 10],
        "rsi_window": [-1, 1],
        "rsi_extreme": [-2, 2]
    }
    
    for param, shift_values in shifts.items():
        for shift in shift_values:
            test_params = best_params.copy()
            test_params[param] += shift
            
            # Ensure constraints remain valid
            if test_params["ema_window"] < 20: continue
            if test_params["rsi_window"] < 2: continue
            if test_params["rsi_extreme"] < 2 or test_params["rsi_extreme"] > 45: continue
                
            strategy = VBTrsiEmaScalper(**test_params)
            portfolio = strategy.backtest(
                close, 
                open_price=open_price,
                init_cash=10000,
                fees=0.0006,
                slippage=0.0001,
                tp_stop=0.002,
                freq='1m'
            )
            
            test_return = portfolio.total_return()
            
            # Calculate relative performance drop
            if base_return > 0:
                drop_pct = (base_return - test_return) / base_return
            else:
                # If base return is negative, a more negative test return is a drop
                drop_pct = (test_return - base_return) / abs(base_return) if base_return != 0 else 0
                
            if drop_pct > max_drop:
                max_drop = drop_pct
                
            if drop_pct > 0.30: # 30% relative drop threshold
                logger.warning(f"FRAGILITY DETECTED: Shifting {param} by {shift} caused performance to drop by {drop_pct*100:.1f}%")
                fragile = True
                
    if not fragile:
        logger.info(f"Sensitivity Audit Passed. Max relative performance drop: {max_drop*100:.1f}%")
        
    return fragile, max_drop

def main():
    logger = setup_logging()
    logger.info("Starting Genetic Algorithm Optimization with Optuna...")
    
    close, open_price = get_data()
    if close.empty:
        logger.error("No data available in SQLite database.")
        return
        
    # Configure Genetic Algorithm Sampler (NSGA-II)
    # This specifically codifies Selection, Crossover, and Mutation.
    sampler = optuna.samplers.NSGAIISampler(
        population_size=20, # Define generation size for Selection
        mutation_prob=0.1,  # 10% random mutation to avoid local optima
        crossover_prob=0.9  # 90% chance to combine successful parent traits
    )
    
    # Create the optimization study
    study = optuna.create_study(
        study_name="BTCUSD_GA_Optimization",
        direction="maximize", # We want highest total return
        sampler=sampler
    )
    
    # Run optimization for 100 trials (5 generations)
    n_trials = 100
    logger.info(f"Running evolutionary search for {n_trials} trials...")
    
    # Optimize
    study.optimize(create_objective(close, open_price), n_trials=n_trials, show_progress_bar=False)
    
    # Output Results
    print("\n" + "="*50)
    print("      GENETIC OPTIMIZATION COMPLETE")
    print("="*50)
    print(f"Best Total Return: {study.best_value * 100:.2f}%")
    print("Best Parameters (The 'Winning Genes'):")
    for key, value in study.best_params.items():
        print(f"  {key}: {value}")
    print("="*50)
    print("="*50)
    
    # Run Stability Audit
    is_fragile, max_drop = audit_parameter_sensitivity(study.best_params, study.best_value, close, open_price, logger)
    
    # Save to JSON for Out-of-Sample Prep
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "best_strategy_params.json")
    
    payload = {
        "parameters": study.best_params,
        "base_return": study.best_value,
        "is_fragile": is_fragile,
        "max_sensitivity_drop": max_drop
    }
    
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=4)
        
    logger.info(f"Best parameters saved to {out_path} for future Out-of-Sample validation.")
    logger.info("Optimization finished.")

if __name__ == "__main__":
    main()
