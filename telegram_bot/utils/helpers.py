import logging
from telegram import Update, User
from typing import Optional

logger = logging.getLogger(__name__)

def get_user_mention(user: User) -> str:
    """Returns a markdown mention for a user."""
    if user.username:
        return f"@{user.username}"
    else:
        return user.mention_markdown_v2()

def get_group_id(update: Update) -> Optional[int]:
    """Extracts group ID from an update more reliably."""
    if update.effective_chat:
        return update.effective_chat.id
    logger.warning("Could not extract group_id from update.")
    return None

def is_user_admin(update: Update, user_id: int) -> bool:
    """
    Checks if a user is an administrator or owner of the chat.
    This function requires `context.bot` to be available and might need to be
    called from a handler where context is passed.
    For simplicity in some services, we might pass the bot instance directly.
    """
    # This is a placeholder. A real implementation needs access to bot.get_chat_member or similar.
    # This check often needs to be asynchronous.
    # Consider using context.bot.get_chat_member(chat_id, user_id) in an async function.
    # For now, this is a simplified synchronous version that might not always work or be accurate.
    # It's better to use the one in permissions.py for actual permission checking.
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        # In a real scenario, you'd use:
        # member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        # return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        # For this example, we'll assume a simplified check or that this helper
        # is used in contexts where admin status is already known or less critical.
        logger.warning("is_user_admin in helpers.py is a placeholder and should be used with caution.")
        # This will likely not work as intended without `context.bot`.
        # Returning False by default to be safe.
        return False
    return False


if __name__ == "__main__":
    # This part is for testing or direct execution, which is unlikely for helpers.
    logger.info("Helpers module loaded. Contains utility functions.")
    # Example (conceptual, as User object needs to be created appropriately):
    # from telegram import User
    # test_user_with_username = User(id=1, first_name="Test", is_bot=False, username="testuser")
    # test_user_without_username = User(id=2, first_name="Test NoUser", is_bot=False)
    # logger.info(f"Mention for user with username: {get_user_mention(test_user_with_username)}")
    # logger.info(f"Mention for user without username: {get_user_mention(test_user_without_username)}")
    pass
