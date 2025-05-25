import asyncio
import logging
# from telegram.ext import PicklePersistence # User had this commented
from telegram_bot.config import settings
from telegram_bot.core.logging_config import setup_logging
from telegram_bot.core.bot_setup import register_handlers, post_bot_initialization
from telegram_bot.database.engine import init_db_models
from telegram_bot.database.crud import UserFloodRecordCRUD
from telegram_bot.database.engine import AsyncSessionFactory
from telegram.ext import ApplicationBuilder # Added import
# from telegram import Update # Not needed here as per PTB defaults for allowed_updates

setup_logging()
logger = logging.getLogger(__name__)

async def periodic_cleanup_task():
    while True:
        await asyncio.sleep(3600 * 6) 
        logger.info("شروع وظیفه پاکسازی دوره‌ای رکوردهای ضد سیلاب...")
        try:
            async with AsyncSessionFactory() as session:
                await UserFloodRecordCRUD.clear_old_records(session, older_than_seconds=3600 * 24)
            logger.info("وظیفه پاکسازی دوره‌ای با موفقیت انجام شد.")
        except Exception as e:
            logger.error(f"خطا در وظیفه پاکسازی دوره‌ای: {e}", exc_info=True)

async def main() -> None:
    logger.info(f"ربات با توکن: ...{settings.BOT_TOKEN[-6:] if settings.BOT_TOKEN else 'None'} در حال راه‌اندازی است.")
    logger.info(f"آدرس پایگاه داده: {settings.DATABASE_URL}")
    logger.info(f"مدیران اصلی ربات: {settings.OWNER_IDS}")
    logger.info(f"محیط اجرایی: {settings.ENVIRONMENT}")

    await init_db_models()

    # persistence = PicklePersistence(filepath="bot_persistence.pickle") # User had this commented

    application_builder = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        # .persistence(persistence) 
        .post_init(post_bot_initialization) 
        # .concurrent_updates(True) 
        # .connection_pool_size(10) 
    )
    application = application_builder.build()

    register_handlers(application)

    logger.info("ربات در حال آماده‌سازی برای شروع polling...")

    # cleanup_task = asyncio.create_task(periodic_cleanup_task()) # User had this commented

    try:
        await application.initialize()
        await application.start()
        logger.info("ربات با موفقیت راه‌اندازی شد و در حال دریافت به‌روزرسانی‌ها است. برای توقف Ctrl+C را بزنید.")
        await application.updater.start_polling( # type: ignore
            # allowed_updates=Update.ALL_TYPES, # Kept commented as Update is not imported and default is ALL_TYPES
            # drop_pending_updates=True
        )

        stop_event = asyncio.Event()
        await stop_event.wait() 

    except (KeyboardInterrupt, SystemExit):
        logger.info("درخواست توقف ربات دریافت شد...")
    except Exception as e:
        logger.critical(f"خطای بحرانی در سطح بالای برنامه هنگام اجرای ربات: {e}", exc_info=True)
    finally:
        logger.info("در حال متوقف کردن ربات و پاکسازی منابع...")
        if application.updater and application.updater.running: # type: ignore
            await application.updater.stop() # type: ignore
        if application.running:
            await application.stop()
        # await application.shutdown() # User had this commented

        # if 'cleanup_task' in locals() and not cleanup_task.done(): # User had this commented
        #     cleanup_task.cancel()
        #     try:
        #         await cleanup_task
        #     except asyncio.CancelledError:
        #         logger.info("وظیفه پاکسازی دوره‌ای با موفقیت لغو شد.")

        logger.info("ربات با موفقیت متوقف شد.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e: 
        logger.critical(f"خطای بسیار بحرانی در اجرای asyncio.run(main()): {e}", exc_info=True)
