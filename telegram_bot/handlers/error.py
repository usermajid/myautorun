import logging
import html
import json
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.core.constants import DEVELOPER_CHAT_ID # For sending detailed error reports

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs errors and sends a detailed message to the developer."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # If the update is an Update object, try to get more context
    if isinstance(update, Update):
        chat_info = update.effective_chat.title if update.effective_chat else "N/A"
        user_info = update.effective_user.name if update.effective_user else "N/A"
        update_details = f"Update: {update.to_dict()}\nChat: {chat_info} ({update.effective_chat.id if update.effective_chat else 'N/A'})\nUser: {user_info} ({update.effective_user.id if update.effective_user else 'N/A'})"
    else:
        update_details = f"Update object type: {type(update)}, content: {str(update)}"


    # Format the traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Prepare the message for the developer
    error_message = (
        f"⚠️ An exception occurred! ⚠️\n\n"
        f"{update_details}\n\n"
        f"Error: {html.escape(str(context.error))}\n\n"
        f"Traceback:\n<pre>{html.escape(tb_string)}</pre>"
    )

    # Send the error message to the developer chat ID
    if DEVELOPER_CHAT_ID:
        try:
            # Split message if too long
            max_len = 4096 # Telegram message length limit
            if len(error_message) > max_len:
                chunks = [error_message[i:i + max_len] for i in range(0, len(error_message), max_len)]
                for chunk in chunks:
                    await context.bot.send_message(
                        chat_id=DEVELOPER_CHAT_ID,
                        text=chunk,
                        parse_mode='HTML'
                    )
            else:
                await context.bot.send_message(
                    chat_id=DEVELOPER_CHAT_ID,
                    text=error_message,
                    parse_mode='HTML'
                )
            logger.info(f"Error report sent to developer chat ID {DEVELOPER_CHAT_ID}.")
        except Exception as e:
            logger.error(f"Failed to send error report to developer: {e}", exc_info=True)
    else:
        logger.warning("DEVELOPER_CHAT_ID not set. Cannot send error report.")

    # Optionally, send a generic message to the user if it's a command/callback query
    if isinstance(update, Update) and (update.message or update.callback_query):
        user_message = "Sorry, something went wrong. The developers have been notified."
        try:
            if update.callback_query:
                await update.callback_query.answer(user_message, show_alert=True) # For callback queries
            elif update.message:
                await update.message.reply_text(user_message) # For regular messages
        except Exception as e:
            logger.error(f"Failed to send generic error message to user: {e}", exc_info=True)


if __name__ == "__main__":
    # This part is for testing or direct execution, which is unlikely for handlers.
    from telegram_bot.core.logging_config import setup_logging
    setup_logging() # Configure logging
    logger.info("Error handler module loaded.")
    # To test this, you would typically raise an exception within a mock update flow.
    # Example (conceptual):
    # class MockBot:
    #     async def send_message(self, chat_id, text, parse_mode):
    #         logger.info(f"MockBot sending message to {chat_id}: {text[:100]}...") # Log snippet
    # class MockContext:
    #     def init(self):
    #         self.error = None
    #         self.bot = MockBot()
    # class MockUpdate:
    #     def init(self):
    #         self.effective_chat = None
    #         self.effective_user = None
    #     def to_dict(self): return {}

    # async def test_error_handler():
    #     mock_update = MockUpdate()
    #     mock_context = MockContext()
    #     try:
    #         raise ValueError("This is a test exception.")
    #     except ValueError as e:
    #         mock_context.error = e
    #         await error_handler(mock_update, mock_context)
    # import asyncio
    # asyncio.run(test_error_handler())
    pass
