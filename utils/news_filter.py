import MetaTrader5 as mt5
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class NewsFilter:
    """
    Blocks trading around high-impact economic news events using the MT5 built-in calendar.
    For XAUUSD, it monitors USD high-impact news.
    """
    
    def __init__(self, use_news_filter: bool = True, currencies: list = None):
        self.use_news_filter = use_news_filter
        self.currencies = currencies if currencies is not None else ["USD"]
        self.event_cache = {}  # event_id -> event info (currency, importance, name)
        self.last_cache_update = None

    def _update_event_cache(self):
        """
        Updates the cached dictionary of events to retrieve currencies and importance.
        """
        try:
            events = mt5.calendar_events()
            if events is not None:
                for ev in events:
                    self.event_cache[ev.id] = {
                        "currency": ev.currency,
                        "importance": ev.importance,
                        "name": ev.name
                    }
                self.last_cache_update = datetime.now()
                logger.info(f"NewsFilter: Cached {len(self.event_cache)} event definitions from MT5 Calendar.")
            else:
                logger.warning("NewsFilter: MT5 calendar_events() returned None.")
        except Exception as e:
            logger.warning(f"NewsFilter: Failed to retrieve calendar events: {e}")

    def is_news_embargo(self, current_time: datetime, window_minutes: int = 5) -> bool:
        """
        Returns True if a high-impact news event is scheduled within current_time +/- window_minutes.
        """
        if not self.use_news_filter:
            return False

        try:
            # Update cache if empty or stale (e.g. daily update)
            if not self.event_cache or (self.last_cache_update and datetime.now() - self.last_cache_update > timedelta(days=1)):
                self._update_event_cache()

            # Define time window
            dt_from = current_time - timedelta(minutes=window_minutes)
            dt_to = current_time + timedelta(minutes=window_minutes)
            
            ts_from = int(dt_from.timestamp())
            ts_to = int(dt_to.timestamp())

            # Query MT5 for calendar values in this window
            values = mt5.calendar_value_history(ts_from, ts_to)
            if values is None or len(values) == 0:
                return False

            for val in values:
                ev_info = self.event_cache.get(val.event_id)
                if ev_info:
                    # 3 is high impact (mt5.CALENDAR_IMPORTANCE_HIGH)
                    if ev_info["currency"] in self.currencies and ev_info["importance"] == 3:
                        logger.info(f"News embargo active: {ev_info['name']} at {datetime.fromtimestamp(val.time)}")
                        return True
                else:
                    # Cache miss: try to retrieve all event definitions again
                    self._update_event_cache()
                    ev_info = self.event_cache.get(val.event_id)
                    if ev_info and ev_info["currency"] in self.currencies and ev_info["importance"] == 3:
                        logger.info(f"News embargo active (uncached): {ev_info['name']} at {datetime.fromtimestamp(val.time)}")
                        return True
                        
            return False

        except Exception as e:
            # Fallback gracefully
            logger.warning(f"NewsFilter: Exception in news filter check ({e}). Defaulting to FALSE (no embargo).")
            return False
