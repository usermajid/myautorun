"""
کنترل‌کننده‌های (handlers) مربوط به پیام‌های مختلف در ربات تلگرام.

این ماژول شامل کنترل‌کننده‌هایی برای رویدادهای زیر است:
- پیوستن اعضای جدید به گروه (`handle_new_chat_members`).
- پردازش تمام پیام‌های متنی ارسال شده در گروه‌ها (برای فیلترینگ و کنترل سیلاب) (`process_all_group_messages`).
- خروج اعضا از گروه (`handle_left_chat_member`).
"""
from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.database.engine import AsyncSessionFactory
from telegram_bot.database.crud import GroupSettingCRUD, ForbiddenWordCRUD
from telegram_bot.services.permissions import is_user_admin_or_owner, PermissionService # Updated import
from telegram_bot.services.message_filter import MessageFilterService
from telegram_bot.services.flood_control import FloodControlService
from telegram_bot.utils.helpers import GeneralHelpers
from telegram_bot.core.constants import BotConstants
import logging
import html

logger = logging.getLogger(__name__)

class MessageHandlers:
    """مجموعه‌ای از متدهای استاتیک برای مدیریت رویدادهای مربوط به پیام‌ها."""
    @staticmethod
    async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        مدیریت رویداد پیوستن یک یا چند عضو جدید به گروه.

        - اگر ربات به گروه اضافه شود، پیام راهنما برای ادمین کردن ارسال می‌کند.
        - برای سایر اعضای جدید، پیام خوشامدگویی (بر اساس تنظیمات گروه) ارسال می‌کند.
        """
        if not update.message or not update.message.new_chat_members or not update.effective_chat:
            return

        chat = update.effective_chat
        new_members = update.message.new_chat_members

        async with AsyncSessionFactory() as session:
            group_settings = await GroupSettingCRUD.get_or_create(session, chat.id, chat.title)

        for member in new_members:
            if member.id == context.bot.id:
                logger.info(f"Bot was added to group '{chat.title}' (ID: {chat.id}).")
                PermissionService.clear_permission_cache(chat.id) # Clear cache on being added
                # Optionally, send a message that bot needs to be made admin
                await context.bot.send_message(
                    chat.id,
                    "سلام! از اینکه من را به گروه خود اضافه کردید سپاسگزارم.\n"
                    "برای اینکه بتوانم به درستی کار کنم، لطفاً من را به عنوان **مدیر** گروه انتخاب کرده و مجوزهای لازم (مانند حذف پیام و محدود کردن کاربران) را اعطا نمایید.\n"
                    "پس از آن، می‌توانید از دستور /help برای مشاهده قابلیت‌ها استفاده کنید."
                )
                continue

            user_mention_html = GeneralHelpers.create_user_mention_html(member.id, member)
            chat_title_html = html.escape(chat.title or "گروه")

            welcome_template = group_settings.welcome_message if group_settings and group_settings.welcome_message else BotConstants.DEFAULT_WELCOME_MESSAGE

            final_welcome_message = GeneralHelpers.format_welcome_message(
                welcome_template,
                user_mention_html,
                chat_title_html
            )

            if group_settings and group_settings.rules and group_settings.rules != BotConstants.DEFAULT_RULES_TEXT:
                 final_welcome_message += f"\n\n📜 لطفاً قوانین گروه را با دستور /rules مطالعه فرمایید."

            try:
                await update.message.reply_html(final_welcome_message, disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Error sending welcome message to {member.id} in group {chat.id}: {e}")

            logger.info(f"User {member.full_name} (ID: {member.id}) joined group {chat.id}.")

    @staticmethod
    async def process_all_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        پردازش تمام پیام‌های متنی ارسال شده در گروه‌ها (به جز پیام‌های ادمین‌ها).

        این تابع به ترتیب موارد زیر را انجام می‌دهد:
        1. بررسی و اعمال قوانین ضد سیلاب (Anti-flood).
        2. در صورت عدم تشخیص سیلاب، اعمال فیلترهای محتوا (لینک، فروارد، کلمات ممنوعه).
        """
        if not update.message or not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
            return
        if not update.effective_user: # Should not happen for messages, but good check
            return

        # Ignore messages from admins for filtering and flood control
        if await is_user_admin_or_owner(update, context): # Updated call
            return

        # 1. Flood Control
        if await FloodControlService.check_and_handle_flood(update, context):
            return  # User was muted due to flood, no further processing needed

        # 2. Message Filtering
        filter_service = MessageFilterService(update, context)
        await filter_service.init_permissions() # Check bot's permission to delete

        # filter_message() will internally fetch group_settings and forbidden_words if needed.
        if await filter_service.filter_message():
            return  # Message was filtered (e.g., deleted)

    @staticmethod
    async def handle_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        مدیریت رویداد خروج یک عضو از گروه.

        در صورت فعال بودن در تنظیمات گروه، پیام بدرقه برای عضو خارج شده ارسال می‌کند.
        برای ربات‌ها پیام بدرقه ارسال نمی‌شود.
        """
        if not update.message or not update.message.left_chat_member or not update.effective_chat:
            logger.debug("Left member handler: No left member or effective_chat.")
            return

        member = update.message.left_chat_member
        chat = update.effective_chat
        
        # Optional: Don't send farewell message for bots
        if member.is_bot:
            logger.info(f"Bot {member.username or member.id} left chat {chat.id}. Skipping farewell message.")
            return

        async with AsyncSessionFactory() as session:
            group_settings = await GroupSettingCRUD.get_or_create(session, chat.id, chat.title)
        
        if group_settings and group_settings.farewell_message_active and group_settings.farewell_message:
            user_mention_html = GeneralHelpers.create_user_mention_html(member.id, member)
            chat_title_html = html.escape(chat.title or "گروه")

            farewell_msg = GeneralHelpers.format_welcome_message( # Reusing format_welcome_message for placeholders
                group_settings.farewell_message,
                user_mention_html,
                chat_title_html
            )
            try:
                await context.bot.send_message(chat_id=chat.id, text=farewell_msg, parse_mode='HTML')
                logger.info(f"Sent farewell message for member {member.id} in chat {chat.id}")
            except Exception as e:
                logger.error(f"Error sending farewell message for {member.id}: {e}", exc_info=True)
