from abc import ABC, abstractmethod
import pandas as pd

class TradingStrategy(ABC):
    """
    Abstract Base Class for all trading strategies.
    Defines the standard interface for indicator calculation and signal generation.
    """
    
    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators required for the strategy.
        Must return a DataFrame with the indicators added as columns.
        """
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell signals based on calculated indicators.
        Must return a DataFrame with a 'signal' column (1: Buy, -1: Sell, 0: Hold).
        """
        pass
