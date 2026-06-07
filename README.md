# RoboBTC: High-Frequency Bitcoin Trading Infrastructure

A professional-grade algorithmic trading system for BTCUSD using the MetaTrader 5 Python API and Exness brokerage.

## Features

- **Direct MT5 Integration**: Low-latency communication with the MT5 terminal.
- **Robust Data Engineering**: Continuous tick and OHLCV data harvesting.
- **Advanced Strategies**: Statistical arbitrage (Mean Reversion) and Trend Following logic.
- **Mathematical Risk Management**: Implementation of the Kelly Criterion for optimal position sizing.
- **Security**: Environment-based credential management.
- **Resilience**: Watchdog and Kill Switch mechanisms for 24/7 uptime.
- **Monitoring**: Prometheus/Grafana integration for real-time observability.

## Installation

1. Install Python 3.9+.
2. Install MetaTrader 5 Terminal (Exness).
3. Clone this repository.
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Configure your `.env` file with your Exness credentials.

## Project Structure

- `config/`: Configuration and sensitive data management.
- `core/`: MT5 API bridge and account monitoring.
- `data/`: Data harvesting and local persistence.
- `strategies/`: Alpha research and strategy implementation.
- `backtesting/`: Historical validation using `vectorbt`.
- `execution/`: Order management and risk control.
- `monitoring/`: Logging and metrics exportation.
- `scripts/`: Resilience and emergency tools.

## Add symbols
- btc_config.py -> ACTIVE_SYMBOLS = ["BTCUSDc", "XAUUSDc", "BTCUSDm", "XAUUSDm"]
- .env -> EXNESS_SYMBOL=BTCUSDc,XAUUSDc

## Roadmap

Developed over a 365-day horizon:
- **Q1**: Infrastructure and Data Engineering.
- **Q2**: Alpha Research and Backtesting.
- **Q3**: Risk Management and System Integration.
- **Q4**: Deployment and Scaling.

## License

MIT
