import asyncio
import logging

from telegram_bot.main import main

# Logger for this main.py, if needed for shutdown messages, etc.
# The main application logging is handled within telegram_bot.main
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # It's good practice to still log this at the root level
        logger.info("Bot shutdown requested via KeyboardInterrupt.")
    except Exception as e:
        # Critical errors that prevent the app from starting or cause it to crash
        # should also be logged at the root level.
        logger.critical(f"Application failed to run: {e}", exc_info=True)
