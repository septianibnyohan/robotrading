import MetaTrader5 as mt5
import logging
import time
from config.credentials import get_mt5_credentials

logger = logging.getLogger(__name__)

class MT5Bridge:
    """
    Handles initialization and connection to the MT5 terminal.
    """
    def             __init__(self):
        self.credentials = get_mt5_credentials()

    def connect(self):
        """
        Initializes and logs into the MT5 terminal.
        """
        if not mt5.initialize():
            logger.error(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
        
        login_result = mt5.login(
            login=self.credentials['login'],
            password=self.credentials['password'],
            server=self.credentials['server']
        )
        
        if not login_result:
            logger.error(f"Failed to login to MT5: {mt5.last_error()}")
            return False
            
        logger.info("Successfully connected to MT5.")
        return True

    def disconnect(self):
        """
        Shuts down the MT5 connection.
        """
        mt5.shutdown()
        logger.info("MT5 connection closed.")

    @staticmethod
    def get_last_error():
        return mt5.last_error()

    def get_account_info(self):
        """
        Retrieves current account information.
        """
        account_info = mt5.account_info()
        if account_info is None:
            logger.error(f"Failed to retrieve account info: {mt5.last_error()}")
            return None
        return account_info._asdict()

    def ensure_connection(self):
        """
        Connection watchdog.
        Catches the (-10005, 'IPC timeout') error if the terminal closes or loses internet.
        Waits 60 seconds, then attempts to re-initialize the connection.
        """
        info = mt5.terminal_info()
        if info is None:
            err = mt5.last_error()
            if err == (-10005, 'IPC timeout'):
                logger.error(f"Watchdog caught error: {err}. MT5 terminal closed or unreachable.")
                logger.info("Waiting 60 seconds before attempting to reconnect...")
                time.sleep(60)
                logger.info("Attempting to re-initialize connection...")
                return self.connect()
            else:
                logger.warning(f"Watchdog encountered unknown error: {err}")
        return True
