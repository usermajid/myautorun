from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.database.engine import AsyncSessionFactory
from telegram_bot.database.crud import GroupSettingCRUD, ForbiddenWordCRUD
from telegram_bot.services.permissions import PermissionService
from telegram_bot.services.message_filter import MessageFilterService
from telegram_bot.services.flood_control import FloodControlService
from telegram_bot.utils.helpers import GeneralHelpers
from telegram_bot.core.constants import BotConstants
import logging
import html

logger = logging.getLogger(__name__)

class MessageHandlers:
    @staticmethod
    async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        if not update.message or not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
            return
        if not update.effective_user: # Should not happen for messages, but good check
            return

        # Ignore messages from admins for filtering and flood control
        if await PermissionService.is_user_admin_or_owner(update, context):
            return

        # 1. Flood Control
        if await FloodControlService.check_and_handle_flood(update, context):
            return  # User was muted due to flood, no further processing needed

        # 2. Message Filtering
        filter_service = MessageFilterService(update, context)
        await filter_service.init_permissions() # Check bot's permission to delete

        async with AsyncSessionFactory() as session:
            group_settings = await GroupSettingCRUD.get_or_create(session, update.effective_chat.id, update.effective_chat.title)

            # Check for forbidden words
            if group_settings.filter_links_active or group_settings.filter_forwards_active or group_settings.forbidden_words: # Optimization: only fetch words if any filter is active
                forbidden_words_list = await ForbiddenWordCRUD.get_all(session, update.effective_chat.id)
                if await filter_service.filter_forbidden_words(group_settings, forbidden_words_list):
                    return # Message deleted

            # Check for links
            if await filter_service.filter_links(group_settings):
                return # Message deleted

            # Check for forwards
            if await filter_service.filter_forwards(group_settings):
                return # Message deleted
