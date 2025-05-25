import logging
from telegram_bot.config import settings

def setup_logging() -> None:
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    handlers = [logging.StreamHandler()]
    if settings.ENVIRONMENT == "production":
        file_handler = logging.FileHandler("bot_prod.log", encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)

    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=log_format,
        handlers=handlers
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO if settings.LOG_LEVEL <= logging.INFO else settings.LOG_LEVEL)
    logging.getLogger("telegram.bot").setLevel(logging.INFO if settings.LOG_LEVEL <= logging.INFO else settings.LOG_LEVEL)

    logger = logging.getLogger(__name__)
    logger.info(f"لاگ‌گیری با سطح {settings.LOG_LEVEL_STR} تنظیم شد. محیط: {settings.ENVIRONMENT}")
