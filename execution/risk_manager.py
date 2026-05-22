class RiskManager:
    """
    Handles position sizing and risk management logic.
    """
    def __init__(self, fractional_kelly=0.5):
        self.fractional_kelly = fractional_kelly

    def calculate_kelly_size(self, win_prob, win_loss_ratio, account_balance):
        """
        Calculates the optimal trade size using the Kelly Criterion.
        f* = (bp - q) / b
        """
        p = win_prob
        q = 1 - p
        b = win_loss_ratio
        
        if b == 0:
            return 0
            
        kelly_f = (b * p - q) / b
        
        # Apply fractional Kelly to reduce variance
        trade_size_percent = max(0, kelly_f * self.fractional_kelly)
        
        return account_balance * trade_size_percent

    def calculate_lot_size(self, risk_amount, price, symbol_info):
        """
        Converts a dollar risk amount into MT5 lots, respecting symbol constraints.
        """
        if price <= 0:
            return 0.0
            
        # Calculate raw lots based on contract size (usually 1 for BTCUSD)
        # Formula: Lots = RiskAmount / (Price * ContractSize)
        raw_lots = risk_amount / (price * symbol_info.trade_contract_size)
        
        # Snap to volume step
        step = symbol_info.volume_step
        lots = (raw_lots // step) * step
        
        # Respect min/max limits
        lots = max(symbol_info.volume_min, min(symbol_info.volume_max, lots))
        
        return round(lots, 2)

    def get_margin_requirement(self, volume, price, leverage, contract_size=1):
        """
        Calculates the margin required for a position.
        Margin = (Volume * ContractSize * MarketPrice) / Leverage
        """
        return (volume * contract_size * price) / leverage
