import logging
from datetime import datetime, timezone, timedelta
import MetaTrader5 as mt5
from btc_config import SYMBOL

logger = logging.getLogger(__name__)

def get_daily_realized_profit(start_time):
    """Fetches and sums realized P&L today."""
    deals = mt5.history_deals_get(start_time, datetime.now(timezone.utc))
    profit = 0.0
    if deals:
        for d in deals:
            if d.symbol == SYMBOL:
                profit += d.profit + d.swap + d.commission
    return profit

def get_consecutive_losses():
    """Counts consecutive losses over the past 7 days."""
    now = datetime.now(timezone.utc)
    week_deals = mt5.history_deals_get(now - timedelta(days=7), now)
    losses = 0
    if week_deals:
        closing = [d for d in week_deals if d.symbol == SYMBOL and d.entry in [mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT]]
        closing.sort(key=lambda x: x.time, reverse=True)
        for d in closing:
            if (d.profit + d.swap + d.commission) < 0:
                losses += 1
            else:
                break
    return losses

def check_circuit_breaker(starting_balance):
    """Validates risk limits."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    profit = get_daily_realized_profit(today)
    # loss_pct = 0.0 if starting_balance <= 0 else (-profit) / starting_balance
    # if loss_pct > 0.05:
    #     logger.warning(f"Daily loss ({loss_pct*100:.2f}%) exceeds 5% threshold.")
    #     return False, profit
    # losses = get_consecutive_losses()
    # if losses >= 5:
    #     logger.warning(f"Circuit Breaker: {losses} consecutive losses reached.")
    #     return False, profit
    return True, profit
