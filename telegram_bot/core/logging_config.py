"""
پیکربندی سیستم لاگ‌گیری (Logging) برای برنامه ربات.

این ماژول یک تابع `setup_logging` را ارائه می‌دهد که باید در ابتدای برنامه
فراخوانی شود تا لاگ‌گیری بر اساس تنظیمات مشخص شده در `config.py`
(مانند سطح لاگ، فرمت لاگ، و ذخیره در فایل در محیط production) تنظیم گردد.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from telegram_bot.config import settings

def setup_logging() -> None:
    """
    پیکربندی و راه‌اندازی سیستم لاگ‌گیری برای کل برنامه.

    بر اساس تنظیمات (`settings.LOG_LEVEL`, `settings.ENVIRONMENT`):
    - فرمت لاگ‌ها را تعیین می‌کند.
    - یک StreamHandler برای نمایش لاگ‌ها در کنسول اضافه می‌کند.
    - در محیط 'production'، یک TimedRotatingFileHandler برای ذخیره لاگ‌ها
      در فایل (`bot_prod.log`) با چرخش روزانه و نگهداری تا ۷ فایل پشتیبان، پیکربندی می‌کند.
    - سطح لاگ‌گیری برای لاگرهای خاص (مانند httpx, telegram.ext) را تنظیم می‌کند
      تا از ثبت پیام‌های بیش از حد جلوگیری شود.
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
    handlers = [logging.StreamHandler()]
    if settings.ENVIRONMENT == "production":
        # Configure TimedRotatingFileHandler for daily rotation and 7 backups
        file_handler = TimedRotatingFileHandler(
            "bot_prod.log", 
            when="midnight", 
            backupCount=7, 
            encoding='utf-8'
        )
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
