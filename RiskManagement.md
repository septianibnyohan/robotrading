# Backtesting Walkthrough: BTCUSDc, XAUUSDc & XAGUSDc 3-Year Analysis

We completed 3-year historical backtests for `BTCUSDc`, `XAUUSDc`, and `XAGUSDc` using 1-minute and 5-minute data downloaded directly from MetaTrader 5 (MT5). The code incorporates the revamped basket-risk & cumulative TP calculations.

---

## 1. Backtest Results Summary

| Asset | Timeline | Total Closed Trades | Win Rate | Total Net Return | Max Drawdown | Max Layers Reached |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **BTCUSDc** (Bitcoin) | 36 Months (M1) | 27,868 | 74.57% | $398,716.07 | 6,162.91% | **221 layers** |
| **XAUUSDc** (Gold) | 39 Months (M1) | 12,126 | 79.15% | $21,320.03 | 137.05% | **88 layers** |
| **XAGUSDc** (Silver) | 53 Months (M5) | 2,375 | 81.43% | $9,644.35 | 30.00% | **19 layers** |

---

## 2. XAGUSDc (Silver) Detailed 3-Year Analysis

- **Total Baskets Closed**: 1,707 baskets
- **Max Drawdown**: **30.00%** (Extremely stable drawdown profile)
- **Max Layers Reached**: **19 layers** (Occurred on **Thursday, November 3, 2022**)
- **Win Rate**: **81.43%**

### XAGUSDc Max Layers by Day of the Week
Since the Silver market is closed on weekends, Sunday has no trades, and Saturday represents early morning closes from Friday's sessions:
- **Monday**: 13 layers
- **Tuesday**: **8 layers** (Safest day!)
- **Wednesday**: 14 layers
- **Thursday**: **19 layers** (Highest risk day!)
- **Friday**: **8 layers** (Safest day!)
- **Saturday**: 9 layers
- **Sunday**: 0 layers (market closed)

### XAGUSDc Peak Volatility Dates
1. **2022-11-03** (Thursday): **19 layers**
2. **2026-03-25** (Wednesday): **14 layers**
3. **2023-11-13** (Monday): **13 layers**
4. **2024-12-12** (Thursday): **12 layers**
5. **2022-08-15** (Monday): **11 layers**

The complete day-by-day dataset for Silver can be accessed here: [backtest_XAGUSDc_3y_daily_max_layers.csv](file:///c:/data/project/robobtc/backtest_XAGUSDc_3y_daily_max_layers.csv)

---

## 3. Recommended Safe Days & Safe Times (WIB Time)

To trade with **minimum layers** (avoiding tail risk events), restrict trade openings to the following windows:

### BTCUSDc (Bitcoin) Safe Guidelines
* **Safe Days to Trade**: **Thursday, Saturday, Monday, and Saturday** (Max layers under 34).
  * *Days to Avoid*: **Sunday** (Max 221 layers) and **Friday** (Max 87 layers).
* **Safe Times to Trade (WIB)**:
  * **Late-Night Window (01:00 - 05:00 WIB)**: Max layers: **24**.
  * **Daytime Window (11:00 - 17:00 WIB)**: Max layers: **26**.
  * *Times to Avoid*: **23:00 - 01:00 WIB** (max layers 221) and **05:00 - 06:00 WIB** (max layers 75) and **10:00 - 11:00 WIB** (max layers 87).

### XAUUSDc (Gold) Safe Guidelines
* **Safe Days to Trade**: **Thursday, Friday, Monday, and Saturday** (Max layers under 36).
  * *Days to Avoid*: **Tuesday** (Max 88 layers) and **Wednesday** (Max 43 layers).
* **Safe Times to Trade (WIB)**:
  * **Daytime Window (10:00 - 14:00 WIB)**: Max layers: **17**.
  * **Late-Day Window (16:00 - 02:00 WIB)**: Max layers: **26** (Gold mean-reverts during the US session).
  * *Times to Avoid*: **14:00 - 16:00 WIB** (London morning session open, max layers 88) and **03:00 - 06:00 WIB** (max layers 43) and **08:00 - 10:00 WIB** (max layers 32).

### XAGUSDc (Silver) Safe Guidelines
* **Safe Days to Trade**: **Tuesday, Friday, and Saturday** (Max layers under 9).
  * *Days to Avoid*: **Thursday** (Max 19 layers) and **Wednesday** (Max 14 layers) and **Monday** (Max 13 layers).
* **Safe Times to Trade (WIB)**:
  * **Late-Night Window (00:00 - 03:00 WIB)**: Max layers: **8**.
  * **Morning Window (04:00 - 13:00 WIB)**: Max layers: **11**.
  * *Times to Avoid*: **20:00 - 21:00 WIB** (US open; max layers 19) and **03:00 WIB** (max layers 14) and **23:00 WIB** (max layers 13) and **17:00 WIB** (max layers 12).
