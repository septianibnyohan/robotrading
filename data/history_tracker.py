import json
import os
import logging

logger = logging.getLogger(__name__)

class HistoryTracker:
    """
    Acts as 'memory' for the harvester, recording the exact timestamp 
    of the last successfully downloaded bar for each timeframe.
    """
    def __init__(self, file_path="data/database/history_tracker.json"):
        self.file_path = file_path
        self.state = self._load_state()

    def _load_state(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load history tracker: {e}")
        return {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save history tracker: {e}")

    def get_last_timestamp(self, symbol, timeframe):
        """
        Returns the last successfully harvested timestamp (in seconds).
        Returns None if no history exists.
        """
        return self.state.get(symbol, {}).get(str(timeframe))

    def update_last_timestamp(self, symbol, timeframe, timestamp):
        """
        Updates the tracker with the latest timestamp.
        """
        if symbol not in self.state:
            self.state[symbol] = {}
        
        self.state[symbol][str(timeframe)] = timestamp
        self._save_state()
