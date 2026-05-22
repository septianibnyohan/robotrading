import logging
import sys

def setup_logging(level=logging.INFO):
    """
    Configures structured logging for the application.
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("robobtc.log")
        ]
    )
    
    # Set levels for noisy libraries
    logging.getLogger("MetaTrader5").setLevel(logging.WARNING)
    
    logger = logging.getLogger("robobtc")
    logger.info("Logging initialized.")
    return logger
