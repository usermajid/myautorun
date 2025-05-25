import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from telegram import Update, ChatPermissions # Added ChatPermissions import
from telegram.ext import ContextTypes
from telegram_bot.database import crud
from telegram_bot.database.engine import get_db
from telegram_bot.database.models import GroupSetting, UserFloodRecord

logger = logging.getLogger(__name__)

# This in-memory store is a simple cache. For distributed bots, a more robust solution (e.g., Redis) would be needed.
# Maps: group_id -> user_id -> list of message timestamps
USER_MESSAGE_TIMESTAMPS: Dict[int, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))

class FloodControlService:
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.update = update
        self.context = context
        self.db_session = next(get_db()) # Obtain a DB session

    async def check_and_handle_flood(self) -> bool:
        """Checks for flooding and takes action if necessary. Returns True if flood was detected and handled."""
        if not self.update.message or not self.update.message.from_user or not self.update.effective_chat:
            logger.debug("Flood check skipped: No message, user, or chat.")
            return False

        group_id = self.update.effective_chat.id
        user_id = self.update.message.from_user.id
        current_time = time.time()

        settings: Optional[GroupSetting] = crud.get_or_create_group_setting(self.db_session, group_id)
        if not settings or not settings.flood_control_enabled:
            logger.debug(f"Flood control disabled or no settings for group {group_id}.")
            self.db_session.close()
            return False

        # Clean up old timestamps (older than 1 minute, for example)
        # This simple cleanup might not be efficient for very active groups.
        # A more sophisticated approach might involve periodic cleanup tasks.
        # Also, the flood window (e.g. 60 seconds) should ideally be configurable.
        timestamps = USER_MESSAGE_TIMESTAMPS[group_id][user_id]
        valid_timestamps = [t for t in timestamps if current_time - t < 60] # Keep messages from last 60s
        USER_MESSAGE_TIMESTAMPS[group_id][user_id] = valid_timestamps
        valid_timestamps.append(current_time)

        logger.debug(f"User {user_id} in group {group_id} has {len(valid_timestamps)} messages in the last minute. Max allowed: {settings.max_messages_per_minute}")

        if len(valid_timestamps) > settings.max_messages_per_minute:
            logger.info(f"Flood detected for user {user_id} in group {group_id}.")
            user_flood_record: Optional[UserFloodRecord] = crud.update_user_flood_record(
                self.db_session, group_id, user_id, increment_infraction=True
            )

            if user_flood_record and settings.warn_on_infraction:
                try:
                    await self.update.message.reply_text(
                        f"{self.update.message.from_user.mention_markdown_v2()}, you're sending messages too fast! Please slow down."
                    )
                except Exception as e:
                    logger.error(f"Error sending flood warning message: {e}", exc_info=True)


            if user_flood_record and user_flood_record.infraction_count >= settings.infraction_count_for_action:
                action_taken = False
                if settings.kick_on_infraction and not action_taken: # Prioritize ban if both are true
                    try:
                        await self.context.bot.kick_chat_member(chat_id=group_id, user_id=user_id)
                        logger.info(f"Kicked user {user_id} from group {group_id} due to flooding.")
                        # Optionally, unban after a short period if it's a kick, not a ban.
                        # This requires more complex logic, e.g., using context.job_queue.
                        action_taken = True
                    except Exception as e:
                        logger.error(f"Error kicking user {user_id} for flooding: {e}", exc_info=True)

                if settings.ban_on_infraction: # This implies a permanent ban as per typical Telegram bot actions
                    try:
                        await self.context.bot.ban_chat_member(chat_id=group_id, user_id=user_id)
                        logger.info(f"Banned user {user_id} from group {group_id} due to flooding.")
                        action_taken = True
                    except Exception as e:
                        logger.error(f"Error banning user {user_id} for flooding: {e}", exc_info=True)
                
                if action_taken:
                     # Reset infractions after action is taken
                    crud.reset_user_infraction_count(self.db_session, group_id, user_id)


            # Temporary restriction as an alternative or additional measure
            # For example, restrict user from sending messages for a while
            # This is a more nuanced approach than kick/ban for repeated minor flood
            # For example, restrict for 5 minutes
            # permissions = ChatPermissions(can_send_messages=False)
            # try:
            #     await self.context.bot.restrict_chat_member(
            #         chat_id=group_id,
            #         user_id=user_id,
            #         permissions=permissions
            #     )
            #     logger.info(f"Temporarily restricted user {user_id} in group {group_id} due to flooding.")
            #     # Optionally, schedule a job to lift the restriction later
            #     # self.context.job_queue.run_once(callback_to_lift_restriction, 300, data={'chat_id': group_id, 'user_id': user_id})
            # except Exception as e:
            #     logger.error(f"Error restricting user {user_id}: {e}", exc_info=True)


            self.db_session.close()
            return True # Flood detected and handled

        self.db_session.close()
        return False # No flood detected

    async def unban_user_after_timeout(self, context: ContextTypes.DEFAULT_TYPE):
        """Callback to unban a user after a timeout (if kick was temporary)."""
        job = context.job
        if job and job.data:
            chat_id = job.data.get("chat_id")
            user_id = job.data.get("user_id")
            if chat_id and user_id:
                try:
                    await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
                    logger.info(f"Automatically unbanned user {user_id} in chat {chat_id} after timeout.")
                except Exception as e:
                    logger.error(f"Error unbanning user {user_id} in chat {chat_id} after timeout: {e}", exc_info=True)


if __name__ == "__main__":
    # This part is for testing or direct execution, which is complex for a service like this.
    # It would require mock Update and Context objects.
    from telegram_bot.core.logging_config import setup_logging
    setup_logging() # Configure logging
    logger.info("FloodControlService module loaded. Contains flood detection and handling logic.")
    # Example of how it might be instantiated and used (conceptual):
    # async def main_test():
    #     mock_update = ... # Create a mock Update object
    #     mock_context = ... # Create a mock Context object
    #     flood_service = FloodControlService(mock_update, mock_context)
    #     await flood_service.check_and_handle_flood()
    #
    # import asyncio
    # asyncio.run(main_test())
    pass
