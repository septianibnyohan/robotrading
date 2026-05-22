import csv
import os
from datetime import datetime

class SignalLogger:
    """
    Logs every trading signal evaluation (entries, exits, and filter rejections)
    to a CSV log file for regulatory, compliance, and debugging audits.
    """
    
    def __init__(self, filepath: str = "data/database/signals_log.csv"):
        self.filepath = filepath
        self._ensure_dir()
        self._ensure_header()

    def _ensure_dir(self):
        dir_name = os.path.dirname(self.filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def _ensure_header(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", 
                    "signal_type", 
                    "price", 
                    "spread", 
                    "atr", 
                    "status", 
                    "rejection_reason"
                ])

    def log(self, signal_type: str, price: float, spread: float, atr: float, status: str, rejection_reason: str = ""):
        """
        Appends a signal evaluation event to the CSV log.
        """
        timestamp = datetime.now().isoformat()
        with open(self.filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                signal_type,
                round(price, 5),
                round(spread, 2),
                round(atr, 5) if atr is not None else "",
                status,
                rejection_reason
            ])
