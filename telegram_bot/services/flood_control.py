"""
سرویس کنترل و مدیریت سیلاب پیام (Anti-flood).

این سرویس مسئول شناسایی کاربرانی است که در یک بازه زمانی مشخص، تعداد زیادی پیام ارسال می‌کنند
و اعمال محدودیت‌های لازم (مانند هشدار، اخراج یا مسدود کردن) بر اساس تنظیمات گروه.
از Redis برای ذخیره و شمارش مهرهای زمانی پیام‌ها به صورت مقیاس‌پذیر استفاده می‌کند.
"""
import logging
import time
from typing import Optional

import redis.asyncio as redis # Added
from telegram import Update, ChatPermissions
from telegram.ext import ContextTypes

from telegram_bot.config import settings as app_settings # Added
from telegram_bot.core.constants import BotConstants, BotMessages
from telegram_bot.database import crud
from telegram_bot.database.engine import AsyncSessionFactory
from telegram_bot.database.models import GroupSetting, UserFloodRecord
from telegram_bot.utils.helpers import GeneralHelpers

logger = logging.getLogger(__name__)

# USER_MESSAGE_TIMESTAMPS removed

class FloodControlService:
    """
    منطق مربوط به کنترل سیلاب پیام‌ها را در یک گروه خاص مدیریت می‌کند.

    این کلاس با دریافت آپدیت و کانتکست تلگرام مقداردهی اولیه شده و
    متد `check_and_handle_flood` آن وظیفه اصلی بررسی و اقدام در صورت
    تشخیص سیلاب را بر عهده دارد.
    """
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        مقداردهی اولیه سرویس کنترل سیلاب.

        Args:
            update: آپدیت دریافتی از تلگرام.
            context: کانتکست ربات تلگرام.
        """
        self.update = update
        self.context = context
        self.redis_client: Optional[redis.Redis] = None
        if app_settings.REDIS_HOST:
            try:
                self.redis_client = redis.Redis(
                    host=app_settings.REDIS_HOST,
                    port=app_settings.REDIS_PORT,
                    db=app_settings.REDIS_DB,
                    password=app_settings.REDIS_PASSWORD,
                    decode_responses=True, # Convenient for keys and members
                    socket_timeout=5, # Added timeout
                    socket_connect_timeout=5 # Added timeout
                )
                logger.info("Redis client initialized for FloodControlService.")
            except Exception as e:
                logger.error(f"Failed to initialize Redis client for FloodControlService: {e}", exc_info=True)
                self.redis_client = None # Ensure it's None on failure
        else:
            logger.warning("REDIS_HOST not configured. Redis-based flood control will be inactive.")


    async def check_and_handle_flood(self) -> bool:
        """Checks for flooding and takes action if necessary. Returns True if flood was detected and handled."""
        if not self.update.message or not self.update.message.from_user or not self.update.effective_chat:
            logger.debug("Flood check skipped: No message, user, or chat.")
            return False

        group_id = self.update.effective_chat.id
        user_id = self.update.message.from_user.id
        
        async with AsyncSessionFactory() as session: # Acquire async session for DB operations
            group_settings: Optional[GroupSetting] = await crud.GroupSettingCRUD.get_or_create(session, group_id, self.update.effective_chat.title)
            if not group_settings or not group_settings.anti_flood_active:
                logger.debug(f"Flood control disabled or no settings for group {group_id}.")
                return False

            if not self.redis_client:
                logger.warning(f"Redis client not available. Skipping Redis-based flood check for group {group_id}.")
                # Fallback to no flood detection or potentially old mechanism if desired, but task asks for Redis replacement.
                return False

            current_time = time.time()
            redis_key = f"flood_control:{group_id}:{user_id}"
            flood_window_seconds = BotConstants.FLOOD_TIME_WINDOW_SECONDS # Or from group_settings if configurable

            message_count = 0
            try:
                async with self.redis_client.pipeline() as pipe:
                    # Add current message timestamp. Member is string to ensure uniqueness if time.time() returns same float.
                    # Score is the float timestamp for range queries.
                    await pipe.zadd(redis_key, {str(current_time): current_time})
                    # Remove timestamps older than the flood window
                    await pipe.zremrangebyscore(redis_key, '-inf', current_time - flood_window_seconds)
                    # Count messages in the current window
                    await pipe.zcard(redis_key)
                    # Set/update expiry for the key to clean up inactive records
                    await pipe.expire(redis_key, flood_window_seconds + 60) # e.g., window + 1 minute buffer
                    
                    results = await pipe.execute()
                    message_count = results[2] # zcard result
                
                logger.debug(f"User {user_id} in group {group_id} has {message_count} messages in the last {flood_window_seconds}s (Redis). Max allowed: {group_settings.max_messages_per_minute}")

            except redis.RedisError as e:
                logger.error(f"Redis error during flood check for user {user_id} in group {group_id}: {e}", exc_info=True)
                # If Redis fails, we might choose to not enforce flood control or have a fallback.
                # For now, we'll log and not detect flood to prevent false positives if Redis is down.
                return False


            if message_count > group_settings.max_messages_per_minute:
                logger.info(f"Flood detected for user {user_id} in group {group_id} via Redis ({message_count} > {group_settings.max_messages_per_minute}).")
                
                user_flood_record: Optional[UserFloodRecord] = await crud.UserFloodRecordCRUD.update(
                    session, group_id, user_id, update_last_infraction_timestamp=True, increment_infraction=True
                )

                warn_message = BotMessages.FLOOD_WARNING_MESSAGE.format(
                    user_mention=GeneralHelpers.create_user_mention_html(user_id, self.update.message.from_user)
                )

                if user_flood_record and group_settings.warn_on_infraction:
                    try:
                        await self.update.message.reply_html(warn_message)
                    except Exception as e:
                        logger.error(f"Error sending flood warning message: {e}", exc_info=True)

                if user_flood_record and user_flood_record.infraction_count >= group_settings.infraction_count_for_action:
                    action_taken = False
                    action_log_message = ""

                    # Determine action based on settings (ban highest priority, then kick)
                    # This logic can be expanded (e.g., temporary mute first)
                    if group_settings.ban_on_infraction:
                        try:
                            await self.context.bot.ban_chat_member(chat_id=group_id, user_id=user_id)
                            action_log_message = f"Banned user {user_id} from group {group_id} due to flooding."
                            action_taken = True
                        except Exception as e:
                            logger.error(f"Error banning user {user_id} for flooding: {e}", exc_info=True)
                            await self.update.message.reply_text(BotMessages.BOT_NOT_ADMIN_ENOUGH_BAN)


                    elif group_settings.kick_on_infraction and not action_taken: # Only kick if ban is not set or failed
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
