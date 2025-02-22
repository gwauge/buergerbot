import os
import logging
from datetime import date
from dotenv import load_dotenv
from telegram_logging import TelegramFormatter, TelegramHandler

# Mapping of German month names to numbers
GERMAN_MONTHS_DICT = {
    "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6,
    "Juli": 7, "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12
}


def parse_german_date(day: int, month: str, year: int) -> date:
    return date(year, GERMAN_MONTHS_DICT[month], day)


# check if .env file exists
if not os.path.exists(".env"):
    print("No .env file found")
    exit(1)

# Reads .env file in the current working directory
load_dotenv(dotenv_path=".env", override=True)

LOGGER_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up telegram logging
ENABLE_TELEGRAM = (os.getenv("ENABLE_TELEGRAM") or "0") == "1"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
if ENABLE_TELEGRAM and (not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID):
    print("Telegram token and/or chat ID not found in environment variables")
    exit(1)


def setup_custom_logger(
    console_log_level: int = logging.DEBUG,
    tg_log_level: int = logging.INFO
) -> logging.Logger:
    """Credits: https://stackoverflow.com/a/7622029"""
    logger = logging.getLogger(__name__)
    logger.setLevel(int(os.getenv("LOGGING_LEVEL") or logging.DEBUG))

    # create telegram handler
    if ENABLE_TELEGRAM:
        tg_formatter = TelegramFormatter(
            fmt="%(levelname)s %(message)s",
            datefmt=LOGGER_DATE_FORMAT,
            use_emoji=True
        )

        tg_handler = TelegramHandler(
            bot_token=TELEGRAM_TOKEN,
            chat_id=TELEGRAM_CHAT_ID)
        tg_handler.setFormatter(tg_formatter)
        tg_handler.setLevel(tg_log_level)
        logger.addHandler(tg_handler)

    # create regular console handler
    formatter = logging.Formatter(
        fmt='[%(levelname)s - %(asctime)s] %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(console_log_level)
    logger.addHandler(handler)

    return logger


logger = setup_custom_logger()
