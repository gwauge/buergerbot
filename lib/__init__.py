import os
import logging
from datetime import date
import asyncio
import time

from dotenv import load_dotenv
from telegram_logging import TelegramFormatter, TelegramHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Mapping of German month names to numbers
GERMAN_MONTHS_DICT = {
    "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6,
    "Juli": 7, "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12
}


def parse_german_date(day: int, month: str, year: int) -> date:
    return date(year, GERMAN_MONTHS_DICT[month], day)


# check if .env file exists
if not os.path.exists(".env"):
    print("No .env file found in the current working directory. Relying on environment variables.")
else:
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


async def telegram_send_photo(
    image_bytes: bytes,
    caption: str = "Please solve the captcha and reply with the answer."
) -> str | None:
    """ Send to Telegram using the Bot API """

    if not ENABLE_TELEGRAM:
        logger.warning("Telegram is not enabled")
        return

    # Initialize the bot with your token
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    await application.initialize()
    await application.start()

    # Send the photo
    await application.bot.send_photo(chat_id=TELEGRAM_CHAT_ID, photo=image_bytes, caption=caption)
    # await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=caption)

    captcha_answer: str | None = None

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        nonlocal captcha_answer
        captcha_answer = update.message.text
        logger.debug(f"Received captcha answer: {captcha_answer}")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.updater.start_polling()

    start_time = time.time()

    # Wait for the captcha answer or timeout after 4 minutes and 30 seconds
    while captcha_answer is None and time.time() - start_time < (4 * 60 + 30):
        await asyncio.sleep(0.5)

    # captch was not answered in time
    if captcha_answer is None:
        logger.warning("Captcha answer not received in time")

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

    return captcha_answer


DATE_FORMAT_REGEX = r"^\d{4}-\d{2}-\d{2}$"
TIME_FORMAT_REGEX = "^[0-2][0-9]:[0-5][0-9]$"  # 24-hour format
config_schema = {
    "periodic": {
        "type": "string",
        "regex": TIME_FORMAT_REGEX
    },
    "personal_data": {
        "type": "dict",
        "schema": {
            "foa": {
                "type": "string",
                "allowed": ["herr", "frau", "firma"],
                "required": True
            },
            "first_name": {"type": "string", "required": True},
            "last_name": {"type": "string", "required": True},
            "phone": {"type": "string", "required": True},
            "email": {"type": "string", "required": True},
        }
    },
    "requests": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "id": {"type": "string", "required": True},
                "number_of_people": {"type": "integer", "default": 1, "coerce": int},
            },
        },
    },
    "weekdays": {
        "type": "dict",
        "schema": {
            "monday": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "from": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                        "to": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                    },
                },
                "default": []
            },
            "tuesday": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "from": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                        "to": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                    },
                },
                "default": []
            },
            "wednesday": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "from": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                        "to": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                    },
                },
                "default": []
            },
            "thursday": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "from": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                        "to": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                    },
                },
                "default": []
            },
            "friday": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "from": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                        "to": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                    },
                },
                "default": []
            },
            "saturday": {
                "type": "list",
                "schema": {
                    "type": "dict",
                    "schema": {
                        "from": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                        "to": {"type": "string", "regex": TIME_FORMAT_REGEX, "required": True},
                    },
                },
                "default": []
            }
        }
    },
    "dates": {
        "type": "dict",
        "schema": {
            "earliest": {"type": "string", "regex": DATE_FORMAT_REGEX, "required": False},
            "latest": {"type": "string", "regex": DATE_FORMAT_REGEX, "required": False},
            "exclude": {
                "type": "list",
                "schema": {
                    "type": "string",
                    "regex": DATE_FORMAT_REGEX
                },
                "required": False,
                "default": []
            }
        }
    }
}
