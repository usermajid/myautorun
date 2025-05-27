"""
ماژول تنظیمات برنامه.

این ماژول مسئول بارگذاری تنظیمات از متغیرهای محیطی و فایل .env است.
تنظیمات شامل توکن ربات، اطلاعات اتصال به پایگاه داده، شناسه‌های مالک ربات،
سطح لاگ‌گیری، تنظیمات Redis و سایر پارامترهای پیکربندی برنامه است.
"""
import os
import logging
from dotenv import load_dotenv
from typing import List, Optional

load_dotenv()

class Settings:
    """
    نگهداری و بارگذاری تنظیمات برنامه از متغیرهای محیطی و فایل .env.
    """
    BOT_TOKEN: Optional[str] = os.getenv("BOT_TOKEN")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./default_bot.db")

    _owner_ids_str: Optional[str] = os.getenv("OWNER_IDS")
    OWNER_IDS: List[int] = []
    if _owner_ids_str:
        try:
            OWNER_IDS = [int(id_str.strip()) for id_str in _owner_ids_str.split(',') if id_str.strip()]
        except ValueError:
            logging.error("مقدار OWNER_IDS در فایل .env نامعتبر است. باید لیستی از اعداد جدا شده با کاما باشد.")
            OWNER_IDS = []

    LOG_LEVEL_STR: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_LEVEL: int = getattr(logging, LOG_LEVEL_STR, logging.INFO)

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production").lower()

    REDIS_HOST: Optional[str] = os.getenv("REDIS_HOST")
    _redis_port_str: str = os.getenv("REDIS_PORT", "6379")
    try:
        REDIS_PORT: int = int(_redis_port_str)
    except ValueError:
        logging.warning(f"مقدار REDIS_PORT ('{_redis_port_str}') نامعتبر است. از مقدار پیش‌فرض 6379 استفاده می‌شود.")
        REDIS_PORT: int = 6379

    _redis_db_str: str = os.getenv("REDIS_DB", "0")
    try:
        REDIS_DB: int = int(_redis_db_str)
    except ValueError:
        logging.warning(f"مقدار REDIS_DB ('{_redis_db_str}') نامعتبر است. از مقدار پیش‌فرض 0 استفاده می‌شود.")
        REDIS_DB: int = 0
        
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")

settings = Settings()

if not settings.BOT_TOKEN:
    logging.critical("توکن ربات (BOT_TOKEN) در متغیرهای محیطی یا فایل .env یافت نشد. برنامه متوقف می‌شود.")
    exit()
