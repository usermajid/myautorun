"""
کنترل‌کننده (handler) مربوط به تغییرات وضعیت عضویت ربات در چت‌ها.

این ماژول مسئول رسیدگی به رویداد `my_chat_member` است که نشان‌دهنده
تغییر وضعیت ربات (مانند اضافه شدن به گروه، حذف شدن، ارتقا به ادمین و غیره) می‌باشد.
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from telegram_bot.database.engine import AsyncSessionFactory
from telegram_bot.database.crud import GroupSettingCRUD
from telegram_bot.services.permissions import PermissionService
from telegram_bot.config import settings as app_settings # Renamed to avoid conflict
import logging

logger = logging.getLogger(__name__)

class ChatMemberHandlers:
    """مجموعه‌ای از متدهای استاتیک برای مدیریت رویدادهای مربوط به تغییر وضعیت عضویت ربات."""
    @staticmethod
    async def track_bot_status_in_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        ردیابی و مدیریت تغییرات وضعیت عضویت ربات در یک چت.

        این تابع بر اساس وضعیت جدید ربات (عضو، ادمین، خارج شده، کیک شده)
        اقدامات لازم مانند پاک کردن کش دسترسی‌ها، اطمینان از وجود تنظیمات گروه،
        یا ارسال پیام‌های اطلاع‌رسانی را انجام می‌دهد.
        """
        if not update.my_chat_member:
            return

        result = update.my_chat_member
        chat = result.chat
        old_status = result.old_chat_member.status
        new_status = result.new_chat_member.status

        # Ensure the update is about the bot itself
        if result.new_chat_member.user.id != context.bot.id:
            return

        logger.info(
            f"Bot status in group '{chat.title}' (ID: {chat.id}) changed from "
            f"'{old_status}' to '{new_status}'. "
            f"Change initiated by user: {result.from_user.id} ({result.from_user.full_name})"
        )

        PermissionService.clear_permission_cache(chat.id) # Clear cache on any status change

        if new_status == ChatMemberStatus.MEMBER:
            # Bot was added as a member, but not (yet) an admin
            async with AsyncSessionFactory() as session:
                await GroupSettingCRUD.get_or_create(session, chat.id, chat.title)
            
            if old_status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]: # e.g. was left/kicked
                 # This message is now sent by handle_new_chat_members in message.py
                 # to avoid duplicate messages if bot is added via new_chat_members event.
                 # However, if bot is re-added or permissions change to member, this might be relevant.
                 # For now, we rely on message.py for initial add.
                 pass


        elif new_status == ChatMemberStatus.ADMINISTRATOR:
            # Bot is now an admin
            async with AsyncSessionFactory() as session:
                await GroupSettingCRUD.get_or_create(session, chat.id, chat.title) # Ensure settings exist

            # Check if essential rights are granted and notify
            if await PermissionService.bot_is_admin_with_essential_rights(chat.id, context, notify_chat=True):
                if old_status != ChatMemberStatus.ADMINISTRATOR: # Was not admin before
                    await context.bot.send_message(chat.id, "✅ با موفقیت به عنوان مدیر تنظیم شدم و آماده خدمت‌رسانی هستم!")
            # If not essential rights, bot_is_admin_with_essential_rights would have sent a message

        elif new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
            logger.info(f"Bot was removed or kicked from group '{chat.title}' (ID: {chat.id}).")
            # Optional: Cleanup database settings for this chat if ENVIRONMENT is production
            if app_settings.ENVIRONMENT == "production":
                # Consider if settings should be deleted or just marked inactive
                # For now, we don't delete settings automatically.
                pass
            PermissionService.clear_permission_cache(chat.id) # Ensure cache is cleared
