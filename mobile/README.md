# RoboBTC Mobile

Flutter mobile app for monitoring and controlling the RoboBTC MetaTrader 5 grid/layer trading bot.

## Architecture

### State Management - Riverpod
Mirrors the React frontend's centralized `useState` pattern:

| Provider | Purpose | Polling Interval |
|----------|---------|-----------------|
| `appStateProvider` | Core state (status, positions, history, accounts, config) | 1.5s |
| `backtestStateProvider` | Backtest job status + results | 2s (while running) |
| `logStateProvider` | Terminal log viewer | 2s |

### Data Models
All models map directly to the backend API response format from `C:\data\project\robobtc`:

- **AppStatus** → `/api/status` (MT5 connection, live/forward_test mode state)
- **Position** → `/api/positions` (ticket, symbol, type, volume, profit)
- **Transaction** → `/api/history` (closed trades with reason)
- **SymbolConfig** → `/api/config` (grid parameters: lot size, spacing, TP, max layers)
- **Mt5Account** → `/api/accounts` (login, password, server, symbols)
- **DxyQuote / DxhCandle** → `/api/dxy/*` (dollar index data)
- **BacktestResults** → `/api/backtest/results` (win rate, Sharpe, equity curve)

### Screens

| Screen | Tab Icon | Description |
|--------|----------|-------------|
| Trading Dashboard | Dashboard | Live/sim trading: KPI cards, engine controls, symbol selector, positions table |
| Backtest | Analytics | Historical backtest runner, metrics display, trade list |
| DXY Dashboard | Chart | Dollar index quotes, multi-range chart with EMA 200, harvest button |
| Accounts | Account | MT5 account CRUD configuration |
| Strategy Config | Settings | Per-symbol grid parameter editor (lot size, ATR spacing, risk overrides) |

### UI Design
Dark glassmorphism theme matching the React frontend:
- Background: `#07070F` primary, `#1A1A2E` secondary
- Cards: Semi-transparent blue gradient with border glow
- Accent colors: Green (#00D4AA), Red (#FF4757), Blue (#4A90FF), Yellow (#F5A623), Purple (#BD64FF)
- Custom Canvas painters for all charts (EquityChart, LayerChart, DXYChart)
- Bottom tab navigation optimized for mobile

### API Service
All calls go to `http://<host>:8000`. No authentication (designed for local dev network).

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Bot connection, account states (polled 1.5s) |
| `/api/positions?mode=&login=` | GET | Active positions |
| `/api/history?mode=&login=` | GET | Transaction history |
| `/api/symbols` | GET | Available/active trading symbols |
| `/api/config` | GET | Strategy parameters per symbol |
| `/api/accounts` | GET/POST/DELETE | MT5 account management |
| `/api/control` | POST | Start/stop trading engine |
| `/api/control/close-all` | POST | Emergency close all positions |
| `/api/dxy/*` | GET/POST | Dollar index data + harvest |
| `/api/backtest/*` | GET/POST | Backtest jobs + results |
| `/api/logs?mode=&login=` | GET | Terminal logs |

## Getting Started

### Prerequisites
- Flutter SDK >= 3.12
- Dart SDK >= 3.12

### Run
```bash
flutter pub get
flutter run
```

### Build
```bash
flutter build apk --release
flutter build ios --release
```

## File Structure

```
lib/
├── main.dart                          # App entry, ProviderScope, bottom nav shell
├── core/
│   ├── config.dart                    # API URL, polling intervals
│   └── api/
│       └── api_service.dart           # HTTP client wrapper
├── models/
│   └── data_models.dart               # All DTO classes (Status, Position, etc.)
├── providers/
│   ├── app_provider.dart              # Main state: polling, controls, accounts
│   ├── backtest_provider.dart         # Backtest job tracking
│   └── log_provider.dart              # Log viewer state
├── screens/
│   ├── trading_dashboard_screen.dart  # Live + forward test dashboard
│   ├── backtest_screen.dart           # Backtest runner & results
│   ├── dxy_screen.dart                # DXY index dashboard
│   ├── accounts_screen.dart           # MT5 account CRUD
│   ├── settings_screen.dart           # Strategy parameter editor
│   └── logs_screen.dart               # Terminal-style log viewer
├── theme/
│   └── app_theme.dart                 # Dark glassmorphism design system
├── widgets/
│   ├── kpi_widget.dart                # 5-card KPI row
│   ├── positions_table.dart           # Open positions table
│   ├── history_table.dart             # Filtered transaction history
│   ├── bottom_nav.dart                # Bottom tab navigation
│   └── charts/
│       ├── equity_chart_painter.dart  # Equity curve custom painter
│       ├── layer_chart_painter.dart   # Grid layer visualization
│       └── dxy_chart_painter.dart     # DXY price + EMA 200 chart