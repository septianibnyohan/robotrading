I have completed the 10-year (8.4 years actual) backtest for BTCUSDc (covering February 9, 2018 to July 17, 2026 / 4,421,224 M1 bars) under a fixed spread of 1000 points (10.0 USD), using the volume-scaled spread calculation, and executing exits at the candle's Close price (bar['close']).

All tasks are completed on the 
task.md
 checklist, and I have updated 
walkthrough.md
.

Here are the results:

BTCUSDc (Bitcoin) 10-Year Results (Spread 1000 Points / Exit at Close Price)

- Total Baskets Closed: 11,180 baskets (17,400 individual trades)
- Win Rate: 67.11%
- Total Net Return: **+68,769.86∗∗(onaninitial10,000 balance, which is a 687.7% return in 8.4 years). The strategy generates a positive return every single calendar year tested.
- Max Layers Reached: 234 layers (Occurred on Sunday, December 13, 2020).
- Safe Days to Trade: Tuesday (Max 31 layers), Thursday (Max 30 layers), and Saturday (Max 16 layers).
Days to Avoid: Sunday (Max 234 layers), Friday (Max 98 layers), Wednesday (Max 84 layers), and Monday (Max 70 layers).
- Safe Times to Trade (WIB):
Daytime Window (12:00 - 18:00 WIB): Max layers encountered: 31.
Late-Day Window (12:00 - 20:00 WIB): Max layers encountered: 34.
Late-Night Window (22:00 - 01:00 WIB): Max layers encountered: 16.
Times to Avoid: 01:00 WIB (max layers 234), 21:00 WIB (max layers 168), 04:00 WIB (max layers 98), 11:00 WIB (max layers 84), and 06:00 WIB (max layers 70).

Performance by Calendar Year (BTCUSDc)
Year	Baskets Closed	Max Layers	Net Profit (USD)
2018 (Feb-Dec)	740	30	+$3,670.19
2019	766	31	+$4,242.69
2020	1,242	234	+$2,128.58
2021	1,161	84	+$2,495.63
2022	1,471	98	+$11,891.25
2023	2,208	22	+$8,967.41
2024	1,393	60	+$21,494.05
2025	1,334	168	+$8,594.59
2026 (Jan-Jul)	865	34	+$5,285.48
