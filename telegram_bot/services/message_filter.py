import logging
from typing import Optional, List
from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.database.engine import AsyncSessionFactory # Import AsyncSessionFactory
from telegram_bot.database import crud # Ensure crud refers to async version
from telegram_bot.database.models import GroupSetting
from telegram_bot.services.permissions import PermissionService # Use PermissionService for consistency
from telegram_bot.utils.helpers import GeneralHelpers # For user mentions
from telegram_bot.core.constants import BotMessages # For standard bot messages
import re # Add this import
import logging

logger = logging.getLogger(__name__)

class MessageFilterService:
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.update = update
        self.context = context
        self.bot_can_delete = False # Initialize permission state
        # self.db_session removed

    async def init_permissions(self):
        """Checks and stores if the bot has delete permissions in the current chat."""
        if self.update.effective_chat:
            self.bot_can_delete = await PermissionService.can_bot_delete_messages(self.update.effective_chat.id, self.context)
            if not self.bot_can_delete:
                logger.warning(f"Bot does not have permission to delete messages in chat {self.update.effective_chat.id}.")
        else:
            self.bot_can_delete = False # Should not happen if called correctly

    async def filter_message(self) -> bool:
        """
        Filters messages based on group settings (links, forwards, forbidden words).
        Returns True if the message was deleted or action was taken, False otherwise.
        """
        if not self.update.message or not self.update.effective_chat: # Message text check removed, as some filters don't need it (e.g. forwards)
            logger.debug("Message filter skipped: No message or effective_chat.")
            return False

        group_id = self.update.effective_chat.id
        user = self.update.message.from_user
        user_id = user.id if user else None

        # Admins are typically exempt from message filtering
        if user_id and await PermissionService.is_user_admin_or_owner(self.update, self.context):
            logger.debug(f"User {user_id} is admin in group {group_id}, skipping message filtering.")
            return False

        async with AsyncSessionFactory() as session: # Acquire async session
            settings: Optional[GroupSetting] = await crud.GroupSettingCRUD.get_or_create(session, group_id, self.update.effective_chat.title)
            if not settings:
                logger.warning(f"No settings found for group {group_id}, cannot filter message.")
                return False

            message_deleted = False

            # Filter links
            if settings.filter_links_active and (self.update.message.entities and any(e.type in ["url", "text_link"] for e in self.update.message.entities)):
                logger.info(f"Link detected from user {user_id} in group {group_id}. Deleting message as filter_links_active is True.")
                await self._delete_message_and_warn(BotMessages.LINK_FILTER_WARNING)
                message_deleted = True
            
            # Filter forwards
            if not message_deleted and settings.filter_forwards_active and \
               (self.update.message.forward_from or self.update.message.forward_from_chat or self.update.message.forward_sender_name):
                logger.info(f"Forward detected from user {user_id} in group {group_id}. Deleting message as filter_forwards_active is True.")
                await self._delete_message_and_warn(BotMessages.FORWARD_FILTER_WARNING)
                message_deleted = True

            # Filter forbidden words (only if message has text)
            if not message_deleted and self.update.message.text and settings.filter_forbidden_words_active: # Added check for filter_forbidden_words_active
                forbidden_words_list: List[str] = await crud.ForbiddenWordCRUD.get_all_words_for_group(session, group_id) # Use async
                if forbidden_words_list:
                    message_text_lower = self.update.message.text.lower()
                    for word in forbidden_words_list:
                        # Use whole word matching, case insensitive
                        if re.search(r'\b' + re.escape(word) + r'\b', message_text_lower, re.IGNORECASE):
                            logger.info(f"Forbidden word '{word}' detected from user {user_id} in group {group_id}. Deleting message.")
                            await self._delete_message_and_warn(BotMessages.FORBIDDEN_WORD_WARNING.format(word=word))
                            message_deleted = True
                            break # Stop checking once one forbidden word is found
            
            # Session is automatically closed here
            return message_deleted

    async def _delete_message_and_warn(self, warning_text_template: str):
        """Deletes the current message and optionally warns the user if bot has permission."""
        if not self.update.message or not self.update.effective_chat: return

        # Ensure bot permissions are checked before attempting deletion
        if not self.bot_can_delete:
            logger.warning(f"Skipping message deletion in chat {self.update.effective_chat.id} as bot lacks permission.")
            # Optionally, notify admin or group about lack of permission if this happens frequently
            # await self.context.bot.send_message(self.update.effective_chat.id, BotMessages.BOT_NEEDS_DELETE_PERMISSION)
            return

        try:
            await self.update.message.delete()
            logger.debug(f"Message {self.update.message.message_id} deleted in chat {self.update.effective_chat.id}.")
            
            user_mention = ""
            if self.update.message.from_user:
                 user_mention = GeneralHelpers.create_user_mention_html(self.update.message.from_user.id, self.update.message.from_user)
            
            # Format the warning message, which might include placeholders like {user_mention} or {word}
            # The warning_text_template should be designed to accept these if necessary.
            # For simple warnings, it can be a direct string.
            full_warning = warning_text_template
            if "{user_mention}" in warning_text_template and user_mention:
                full_warning = warning_text_template.format(user_mention=user_mention)
            # If {word} is part of the template, it should have been formatted before calling this method.

            # Consider sending warning as a temporary message or in a less intrusive way
            await self.context.bot.send_message(
                chat_id=self.update.effective_chat.id,
                text=full_warning,
                parse_mode='HTML' # Assuming warnings use HTML
            )
            logger.info(f"Sent warning to chat {self.update.effective_chat.id}: {warning_text_template[:100]}")

        except Exception as e:
            logger.error(f"Error deleting message or sending warning in chat {self.update.effective_chat.id}: {e}", exc_info=True)

# Note: The __main__ block is removed as direct execution of this service module is not typical.
# Testing would be done via integration tests or by running the main bot.
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


