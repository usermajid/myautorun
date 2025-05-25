import logging
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from typing import Optional

logger = logging.getLogger(__name__)

# Permission levels (example, can be expanded)
ADMIN_LEVEL = "administrator"
OWNER_LEVEL = "creator" # Note: Telegram API uses 'creator' for the owner

async def get_user_status_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    """Gets the status of a user in the chat (e.g., member, administrator, creator)."""
    if not update.effective_chat:
        logger.warning("Cannot get user status: effective_chat is None.")
        return None
    try:
        chat_member = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=user_id)
        logger.debug(f"User {user_id} status in chat {update.effective_chat.id}: {chat_member.status}")
        return chat_member.status
    except Exception as e:
        logger.error(f"Error getting chat member status for user {user_id} in chat {update.effective_chat.id}: {e}", exc_info=True)
        return None

async def is_user_admin_or_owner(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: Optional[int] = None) -> bool:
    """Checks if the user (or message sender if user_id is None) is an admin or owner of the chat."""
    if user_id is None:
        if not update.effective_user:
            logger.warning("Cannot check admin status: effective_user is None and no user_id provided.")
            return False
        user_id = update.effective_user.id

    status = await get_user_status_in_chat(update, context, user_id)
    is_admin = status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER, ADMIN_LEVEL, OWNER_LEVEL] # creator is OWNER
    if is_admin:
        logger.info(f"User {user_id} is an admin/owner in chat {update.effective_chat.id if update.effective_chat else 'N/A'}.")
    else:
        logger.info(f"User {user_id} is NOT an admin/owner in chat {update.effective_chat.id if update.effective_chat else 'N/A'} (status: {status}).")
    return is_admin


async def is_bot_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if the bot itself is an administrator in the current chat."""
    if not update.effective_chat:
        logger.warning("Cannot check bot admin status: effective_chat is None.")
        return False
    try:
        bot_member = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=context.bot.id)
        is_admin = bot_member.status == ChatMember.ADMINISTRATOR
        if is_admin:
            logger.info(f"Bot is an admin in chat {update.effective_chat.id}.")
            # You can also check for specific permissions here if needed:
            # if bot_member.can_delete_messages, etc.
        else:
            logger.info(f"Bot is NOT an admin in chat {update.effective_chat.id} (status: {bot_member.status}).")
        return is_admin
    except Exception as e:
        logger.error(f"Error checking if bot is admin in chat {update.effective_chat.id}: {e}", exc_info=True)
        return False

# Example of a higher-order function for permission checks in handlers
def require_admin_privileges(handler_func):
    """Decorator to restrict access to admin users only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            logger.warning("Admin command received without an effective user.")
            # await update.message.reply_text("Could not identify user for permission check.")
            return

        is_admin = await is_user_admin_or_owner(update, context, update.effective_user.id)
        if is_admin:
            return await handler_func(update, context, *args, **kwargs)
        else:
            logger.warning(f"User {update.effective_user.id} ({update.effective_user.name}) tried to use an admin command without privileges in chat {update.effective_chat.id if update.effective_chat else 'N/A'}.")
            if update.message: # Check if update.message is not None
                await update.message.reply_text("You don't have permission to use this command.")
            elif update.callback_query:
                 await update.callback_query.answer("You don't have permission for this action.", show_alert=True)
            return
    return wrapper


if __name__ == "__main__":
    # This section is for conceptual testing.
    # In a real bot, these functions are called within handlers.
    # Setup basic logging for testing this module directly
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("Permissions service module loaded.")

    # To run these async functions, you'd need an event loop:
    # import asyncio
    # async def main_test():
    #     # Mock Update and Context objects would be needed here for a real test
    #     logger.info("Simulating permission checks (requires mock objects or a running bot).")
    #     # e.g., mock_update = ... , mock_context = ...
    #     # await is_user_admin_or_owner(mock_update, mock_context, 123456789)
    # if __name__ == "__main__":
    #    asyncio.run(main_test())
    pass
