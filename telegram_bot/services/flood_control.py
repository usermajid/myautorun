import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from telegram import Update, ChatPermissions # Keep ChatPermissions for potential future use with restrict_chat_member
from telegram.ext import ContextTypes
from telegram_bot.database.engine import AsyncSessionFactory # Import AsyncSessionFactory
from telegram_bot.database import crud # Ensure this refers to the async CRUD module
from telegram_bot.database.models import GroupSetting, UserFloodRecord # Assuming these are still relevant
from telegram_bot.utils.helpers import GeneralHelpers # For user mentions, if needed
from telegram_bot.core.constants import BotConstants, BotMessages # For default messages/settings

logger = logging.getLogger(__name__)

# NB: USER_MESSAGE_TIMESTAMPS is an in-memory store and will not scale across multiple instances
# or persist across restarts. UserFloodRecord.message_timestamps in the DB is not currently used for this time-window check.
# For a scalable solution, a distributed cache like Redis would be more appropriate for tracking message rates.
USER_MESSAGE_TIMESTAMPS: Dict[int, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))

class FloodControlService:
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.update = update
        self.context = context
        # self.db_session removed

    async def check_and_handle_flood(self) -> bool:
        """Checks for flooding and takes action if necessary. Returns True if flood was detected and handled."""
        if not self.update.message or not self.update.message.from_user or not self.update.effective_chat:
            logger.debug("Flood check skipped: No message, user, or chat.")
            return False

        group_id = self.update.effective_chat.id
        user_id = self.update.message.from_user.id
        current_time = time.time()

        async with AsyncSessionFactory() as session: # Acquire async session
            settings: Optional[GroupSetting] = await crud.GroupSettingCRUD.get_or_create(session, group_id, self.update.effective_chat.title)
            if not settings or not settings.anti_flood_active: # Use corrected field name
                logger.debug(f"Flood control disabled or no settings for group {group_id}.")
                return False

            # In-memory message rate tracking (remains for now as per instructions)
            timestamps = USER_MESSAGE_TIMESTAMPS[group_id][user_id]
            # Use BotConstants for flood window or make it configurable in GroupSetting
            flood_window_seconds = BotConstants.FLOOD_TIME_WINDOW_SECONDS 
            valid_timestamps = [t for t in timestamps if current_time - t < flood_window_seconds]
            USER_MESSAGE_TIMESTAMPS[group_id][user_id] = valid_timestamps
            valid_timestamps.append(current_time)

            logger.debug(f"User {user_id} in group {group_id} has {len(valid_timestamps)} messages in the last {flood_window_seconds}s. Max allowed: {settings.max_messages_per_minute}")

            if len(valid_timestamps) > settings.max_messages_per_minute:
                logger.info(f"Flood detected for user {user_id} in group {group_id}.")
                
                # Update user's flood record in the database, including timestamp of this flood detection
                user_flood_record: Optional[UserFloodRecord] = await crud.UserFloodRecordCRUD.update(
                    session, group_id, user_id, update_timestamp=True, increment_infraction=True
                )

                warn_message = BotMessages.FLOOD_WARNING_MESSAGE.format(
                    user_mention=GeneralHelpers.create_user_mention_html(user_id, self.update.message.from_user)
                )

                if user_flood_record and settings.warn_on_infraction:
                    try:
                        await self.update.message.reply_html(warn_message)
                    except Exception as e:
                        logger.error(f"Error sending flood warning message: {e}", exc_info=True)

                if user_flood_record and user_flood_record.infraction_count >= settings.infraction_count_for_action:
                    action_taken = False
                    action_log_message = ""

                    # Determine action based on settings (ban highest priority, then kick)
                    # This logic can be expanded (e.g., temporary mute first)
                    if settings.ban_on_infraction:
                        try:
                            await self.context.bot.ban_chat_member(chat_id=group_id, user_id=user_id)
                            action_log_message = f"Banned user {user_id} from group {group_id} due to flooding."
                            action_taken = True
                        except Exception as e:
                            logger.error(f"Error banning user {user_id} for flooding: {e}", exc_info=True)
                            await self.update.message.reply_text(BotMessages.BOT_NOT_ADMIN_ENOUGH_BAN)


                    elif settings.kick_on_infraction and not action_taken: # Only kick if ban is not set or failed
                        try:
                            await self.context.bot.kick_chat_member(chat_id=group_id, user_id=user_id)
                            # Telegram automatically unbans after a kick, so this is effectively a temporary removal.
                            # If a longer "kick" (ban then unban later) is desired, job_queue is needed.
                            action_log_message = f"Kicked user {user_id} from group {group_id} due to flooding."
                            action_taken = True
                        except Exception as e:
                            logger.error(f"Error kicking user {user_id} for flooding: {e}", exc_info=True)
                            await self.update.message.reply_text(BotMessages.BOT_NOT_ADMIN_ENOUGH_KICK)
                    
                    # If an action was taken, log it and reset infractions in DB
                    if action_taken:
                        logger.info(action_log_message)
                        await crud.UserFloodRecordCRUD.reset_infractions(session, group_id, user_id)
                        # Optionally, notify about the action taken
                        await self.update.message.reply_text(f"{action_log_message.split(' from group')[0]}. تعداد تخلفات صفر شد.")


                # No need to close session explicitly, 'async with' handles it.
                return True # Flood detected and handled

            # No flood detected
            return False
        # Session is automatically closed outside the 'async with' block

    async def unban_user_after_timeout(self, context: ContextTypes.DEFAULT_TYPE):
        """Callback to unban a user after a timeout (if kick was temporary). Currently not used by check_and_handle_flood directly."""
        job = context.job # This is from PTB's JobQueue context
        if job and job.data: # Ensure job and job.data exist
            chat_id = job.data.get("chat_id") # type: ignore
            user_id = job.data.get("user_id") # type: ignore
            if chat_id and user_id:
                try:
                    await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id) # type: ignore
                    logger.info(f"Automatically unbanned user {user_id} in chat {chat_id} after timeout (via job queue).")
                except Exception as e:
                    logger.error(f"Error auto-unbanning user {user_id} in chat {chat_id}: {e}", exc_info=True)

# Note: The __main__ block is removed as direct execution of this service module is not typical.
# Testing would be done via integration tests or by running the main bot.
