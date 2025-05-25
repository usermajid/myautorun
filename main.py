import asyncio
import logging

from telegram.ext import Application

from telegram_bot.config import settings
from telegram_bot.core.logging_config import setup_logging
from telegram_bot.database.engine import init_db_models
from telegram_bot.core.bot_setup import register_handlers, post_bot_initialization

# setup_logging() is called here to ensure logs are configured before any other part of the app runs
setup_logging()
logger = logging.getLogger(__name__)

async def main_async() -> None:  # Renamed to avoid conflict with a potential 'main' variable
    """Starts the bot."""
    logger.info("Starting bot application...")

    # Initialize database models (create tables if they don't exist)
    try:
        await init_db_models()
        logger.info("Database models initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database models: {e}", exc_info=True)
        # Depending on the severity, you might want to exit here
        # For now, we'll log the error and continue, the bot might operate without DB for some features
        # or fail at runtime when DB is accessed.

    # Create the Application and pass it your bot's token.
    application = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        # No persistence for now, can be added later if needed:
        # .persistence(PicklePersistence(filepath="bot_persistence.pickle"))
        .build()
    )

    # Register all handlers (commands, messages, errors, etc.)
    register_handlers(application)
    logger.info("All handlers registered.")

    # Perform post-initialization tasks (e.g., setting bot commands)
    await post_bot_initialization(application)
    logger.info("Post-initialization tasks completed.")

    logger.info("Bot is now polling for updates...")
    # Run the bot until the user presses Ctrl-C
    # We pass 'allowed_updates' to only_listen for specific updates. Default is all.
    await application.run_polling()


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested via KeyboardInterrupt.")
    except Exception as e:
        logger.critical(f"Bot application failed to run: {e}", exc_info=True)
