import logging
from typing import Optional, List
from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.database import crud
from telegram_bot.database.engine import get_db # To get a DB session
from telegram_bot.database.models import GroupSetting
from telegram_bot.services.permissions import is_user_admin_or_owner # Import permission check

logger = logging.getLogger(__name__)

class MessageFilterService:
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.update = update
        self.context = context
        self.db_session = next(get_db()) # Obtain a DB session for the service instance

    async def filter_message(self) -> bool:
        """
        Filters messages based on group settings (links, forwards, forbidden words).
        Returns True if the message was deleted or action was taken, False otherwise.
        """
        if not self.update.message or not self.update.message.text or not self.update.effective_chat:
            logger.debug("Message filter skipped: No message, text, or effective_chat.")
            self.db_session.close()
            return False

        group_id = self.update.effective_chat.id
        user_id = self.update.message.from_user.id if self.update.message.from_user else None

        # Admins are typically exempt from message filtering
        if user_id and await is_user_admin_or_owner(self.update, self.context, user_id):
            logger.debug(f"User {user_id} is admin in group {group_id}, skipping message filtering.")
            self.db_session.close()
            return False

        settings: Optional[GroupSetting] = crud.get_or_create_group_setting(self.db_session, group_id)
        if not settings:
            logger.warning(f"No settings found for group {group_id}, cannot filter message.")
            self.db_session.close()
            return False

        message_deleted = False

        # Filter links
        if not settings.allow_links and (self.update.message.entities and any(e.type in ["url", "text_link"] for e in self.update.message.entities)):
            logger.info(f"Link detected from user {user_id} in group {group_id}. Deleting message as per settings.")
            await self._delete_message_and_warn("Links are not allowed in this group.")
            message_deleted = True
        
        # Filter forwards (approximation, as direct forward detection can be tricky)
        # A common check is if message.forward_from or message.forward_from_chat is not None
        if not message_deleted and not settings.allow_forwards and \
           (self.update.message.forward_from or self.update.message.forward_from_chat or self.update.message.forward_sender_name):
            logger.info(f"Forward detected from user {user_id} in group {group_id}. Deleting message as per settings.")
            await self._delete_message_and_warn("Forwarded messages are not allowed in this group.")
            message_deleted = True

        # Filter forbidden words
        if not message_deleted:
            forbidden_words: List[str] = crud.get_forbidden_words(self.db_session, group_id)
            if forbidden_words: # Only proceed if there are words to check
                message_text_lower = self.update.message.text.lower()
                for word in forbidden_words:
                    if word in message_text_lower: # Simple substring check
                        logger.info(f"Forbidden word '{word}' detected from user {user_id} in group {group_id}. Deleting message.")
                        await self._delete_message_and_warn(f"Your message contains a forbidden word: '{word}'.")
                        message_deleted = True
                        break # Stop checking once one forbidden word is found

        self.db_session.close()
        return message_deleted

    async def _delete_message_and_warn(self, warning_text: str):
        """Deletes the current message and optionally warns the user."""
        try:
            await self.update.message.delete()
            logger.debug(f"Message {self.update.message.message_id} deleted.")
            if self.update.message.from_user: # Only send warning if user is identifiable
                 user_mention = self.update.message.from_user.mention_markdown_v2()
                 full_warning = f"{user_mention}, {warning_text}"
                 # Consider sending warning as a temporary message or in a less intrusive way
                 # For example, send it and schedule its deletion after a few seconds.
                 await self.context.bot.send_message(
                     chat_id=self.update.effective_chat.id,
                     text=full_warning,
                     parse_mode='MarkdownV2'
                 )
                 logger.info(f"Sent warning to user {self.update.message.from_user.id}: {warning_text}")

        except Exception as e:
            logger.error(f"Error deleting message or sending warning: {e}", exc_info=True)


if __name__ == "__main__":
    # This part is for testing or direct execution, which is complex for a service like this.
    # It would require mock Update and Context objects.
    from telegram_bot.core.logging_config import setup_logging
    setup_logging() # Configure logging
    logger.info("MessageFilterService module loaded. Contains message filtering logic.")

    # Example of how it might be instantiated and used (conceptual):
    # async def main_test():
    #     mock_update = ... # Create a mock Update object with a message
    #     mock_context = ... # Create a mock Context object
    #     # Ensure mock_update.message.from_user and mock_update.effective_chat are set
    #     # Also, mock the database interactions or use a test DB
    #
    #     filter_service = MessageFilterService(mock_update, mock_context)
    #     await filter_service.filter_message()
    #
    # import asyncio
    # asyncio.run(main_test())
    pass
