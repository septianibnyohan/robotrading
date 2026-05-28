
import MetaTrader5 as mt5
import logging
import time

logger = logging.getLogger(__name__)

class TradeExecutor:
    """
    Handles order execution via MetaTrader 5.
    """
    def __init__(self, symbol):
        self.symbol = symbol

    def execute_buy(self, volume, stop_loss=None, take_profit=None):
        """
        Sends a BUY market order.
        """
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logger.error(f"Failed to get tick for {self.symbol}")
            return None

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "magic": 123456,
            "comment": "RoboBTC Buy",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if stop_loss:
            request["sl"] = float(stop_loss)
        if take_profit:
            request["tp"] = float(take_profit)

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Buy order failed: {result.comment} (code: {result.retcode})")
        else:
            logger.info(f"BUY order executed: {volume} lots at {tick.ask}")
        
        return result

    def execute_sell(self, volume, stop_loss=None, take_profit=None):
        """
        Sends a SELL market order.
        """
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logger.error(f"Failed to get tick for {self.symbol}")
            return None

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "magic": 123456,
            "comment": "RoboBTC Sell",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if stop_loss:
            request["sl"] = float(stop_loss)
        if take_profit:
            request["tp"] = float(take_profit)

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Sell order failed: {result.comment} (code: {result.retcode})")
        else:
            logger.info(f"SELL order executed: {volume} lots at {tick.bid}")
            
        return result

    def get_open_positions(self):
        """
        Retrieves all open positions for the current symbol.
        """
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return []
        return positions

    def close_position(self, pos):
        """
        Closes a specific open position.
        """
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            logger.error(f"Failed to get tick for closing position {pos.ticket}")
            return None

        type_dict = {
            mt5.POSITION_TYPE_BUY: mt5.ORDER_TYPE_SELL,
            mt5.POSITION_TYPE_SELL: mt5.ORDER_TYPE_BUY
        }
        price_dict = {
            mt5.POSITION_TYPE_BUY: tick.bid,
            mt5.POSITION_TYPE_SELL: tick.ask
        }

        if pos.type not in type_dict:
            logger.error(f"Unknown position type: {pos.type}")
            return None

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": pos.volume,
            "type": type_dict[pos.type],
            "position": pos.ticket,
            "price": price_dict[pos.type],
            "magic": 123456,
            "comment": "RoboBTC Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to close position {pos.ticket}: {result.comment}")
        else:
            logger.info(f"Closed position {pos.ticket}")
        return result

    def close_all_positions(self):
        """
        Closes all open positions for the current symbol.
        """
        positions = self.get_open_positions()
        for pos in positions:
            self.close_position(pos)

    def modify_position_sltp(self, ticket, stop_loss, take_profit):
        """
        Modifies the SL and TP levels of an existing position.
        """
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "symbol": self.symbol,
            "sl": float(stop_loss) if stop_loss is not None else 0.0,
            "tp": float(take_profit) if take_profit is not None else 0.0,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Failed to modify SL/TP for position {ticket}: {result.comment} (code: {result.retcode})")
        else:
            logger.info(f"Successfully modified SL/TP for position {ticket}: SL={stop_loss}, TP={take_profit}")
        return result

