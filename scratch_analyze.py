import pandas as pd
import numpy as np

# Load basket data for XAGUSDc
baskets_path = "backtest_XAGUSDc_baskets.csv"
baskets = pd.read_csv(baskets_path)

# Convert times
baskets['first_trade_open_time'] = pd.to_datetime(baskets['first_trade_open_time'])
baskets['closed_time'] = pd.to_datetime(baskets['closed_time'])

# Extract components (times are in WIB time)
baskets['open_hour'] = baskets['first_trade_open_time'].dt.hour
baskets['open_day'] = baskets['first_trade_open_time'].dt.day_name()
baskets['open_day_num'] = baskets['first_trade_open_time'].dt.dayofweek
baskets['open_date'] = baskets['first_trade_open_time'].dt.date

print("=== OVERALL STATS (XAGUSDc) ===")
print(f"Total baskets closed: {len(baskets)}")
print(f"Max layers reached: {baskets['total_layers'].max()}")
print(f"Mean layers per basket: {baskets['total_layers'].mean():.2f}")
print(f"95th percentile: {baskets['total_layers'].quantile(0.95):.2f}")
print(f"99th percentile: {baskets['total_layers'].quantile(0.99):.2f}")

# Group by day of week
day_stats = baskets.groupby(['open_day_num', 'open_day']).agg(
    basket_count=('total_layers', 'count'),
    max_layers=('total_layers', 'max'),
    mean_layers=('total_layers', 'mean')
).reset_index().sort_values('open_day_num')

print("\n=== MAX LAYERS BY DAY OF WEEK (XAGUSDc) ===")
print(day_stats.to_string(index=False))

# Group by hour
hour_stats = baskets.groupby('open_hour').agg(
    basket_count=('total_layers', 'count'),
    max_layers=('total_layers', 'max'),
    mean_layers=('total_layers', 'mean'),
    percentile_95=('total_layers', lambda x: x.quantile(0.95)),
    percentile_99=('total_layers', lambda x: x.quantile(0.99))
).reset_index()

print("\n=== MAX LAYERS BY HOUR OF DAY (XAGUSDc - WIB) ===")
print(hour_stats.to_string(index=False))

# Safe windows
print("\n=== SAFE WINDOWS ANALYSIS (XAGUSDc) ===")
for window_size in [4, 6, 8, 10, 12]:
    best_max_layers = 999
    best_start_hour = -1
    best_basket_count = 0
    for start_hour in range(24):
        hours_in_window = [(start_hour + h) % 24 for h in range(window_size)]
        window_baskets = baskets[baskets['open_hour'].isin(hours_in_window)]
        if len(window_baskets) > 0:
            window_max = window_baskets['total_layers'].max()
            if window_max < best_max_layers:
                best_max_layers = window_max
                best_start_hour = start_hour
                best_basket_count = len(window_baskets)
    print(f"Best {window_size}-hour window: Start Hour {best_start_hour:02d}:00 WIB, Max Layers: {best_max_layers}, Basket Count: {best_basket_count}")

# Top Dates
date_stats = baskets.groupby('open_date').agg(
    max_layers=('total_layers', 'max'),
    basket_count=('total_layers', 'count')
).reset_index()
top_dates = date_stats.sort_values('max_layers', ascending=False).head(10)
print("\n=== TOP 10 PEAK VOLATILITY DATES (XAGUSDc) ===")
print(top_dates.to_string(index=False))

# Save daily stats
daily_csv = "backtest_XAGUSDc_3y_daily_max_layers.csv"
date_stats.to_csv(daily_csv, index=False)
print(f"\nSaved daily stats to {daily_csv}")
