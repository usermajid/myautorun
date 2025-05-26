from telegram import BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, MessageHandler, ChatMemberHandler, filters, PicklePersistence

# Import handler classes
from telegram_bot.handlers.general import GeneralHandlers
from telegram_bot.handlers.admin import AdminHandlers
from telegram_bot.handlers.message import MessageHandlers
from telegram_bot.handlers.chat_member import ChatMemberHandlers
from telegram_bot.handlers.error import global_error_handler # Direct import of the function

# Import settings if needed for persistence or other setup
from telegram_bot.config import settings
import logging

logger = logging.getLogger(__name__)

async def post_bot_initialization(application: Application) -> None:
    bot_commands = [
        BotCommand("start", "شروع کار با ربات (فقط در چت خصوصی)"),
        BotCommand("help", "نمایش راهنما و لیست کامل دستورات"),
        BotCommand("rules", "نمایش قوانین گروه"),
        BotCommand("setrules", "تنظیم قوانین گروه (مدیران)"),
        BotCommand("setwelcome", "تنظیم پیام خوشامدگویی (مدیران)"),
        BotCommand("kick", "اخراج کاربر (مدیران)"),
        BotCommand("ban", "مسدود کردن کاربر (مدیران)"),
        BotCommand("unban", "رفع مسدودیت کاربر (مدیران)"),
        BotCommand("mute", "سکوت کاربر (مدیران)"),
        BotCommand("unmute", "رفع سکوت کاربر (مدیران)"),
        BotCommand("addword", "افزودن کلمه به فیلتر (مدیران)"),
        BotCommand("delword", "حذف کلمه از فیلتر (مدیران)"),
        BotCommand("listwords", "نمایش کلمات فیلتر شده (مدیران)"),
        BotCommand("togglelinks", "فعال/غیرفعال کردن فیلتر لینک (مدیران)"),
        BotCommand("toggleforwards", "فعال/غیرفعال کردن فیلتر فروارد (مدیران)"),
        BotCommand("toggleantiflood", "فعال/غیرفعال کردن ضد سیلاب (مدیران)"),
    ]
    try:
        await application.bot.set_my_commands(bot_commands)
        await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Default bot commands set successfully in Telegram.")
    except Exception as e:
        logger.error(f"Error setting default bot commands: {e}")


def register_handlers(application: Application) -> None:
    application.add_error_handler(global_error_handler)

    # General Handlers
    application.add_handler(CommandHandler("start", GeneralHandlers.start_command, filters=filters.ChatType.PRIVATE))
    application.add_handler(CommandHandler("help", GeneralHandlers.help_command))
    application.add_handler(CommandHandler("rules", GeneralHandlers.rules_command, filters=filters.ChatType.GROUPS))

    # Admin Handlers (all restricted to group chats)
    group_filter = filters.ChatType.GROUPS
    application.add_handler(CommandHandler("setrules", AdminHandlers.set_rules_command, filters=group_filter))
    application.add_handler(CommandHandler("setwelcome", AdminHandlers.set_welcome_command, filters=group_filter))
    application.add_handler(CommandHandler("kick", AdminHandlers.kick_command, filters=group_filter))
    application.add_handler(CommandHandler("ban", AdminHandlers.ban_command, filters=group_filter))
    application.add_handler(CommandHandler("unban", AdminHandlers.unban_command, filters=group_filter))
    application.add_handler(CommandHandler("mute", AdminHandlers.mute_command, filters=group_filter))
    application.add_handler(CommandHandler("unmute", AdminHandlers.unmute_command, filters=group_filter))
    application.add_handler(CommandHandler("addword", AdminHandlers.add_forbidden_word_command, filters=group_filter))
    application.add_handler(CommandHandler("delword", AdminHandlers.remove_forbidden_word_command, filters=group_filter))
    application.add_handler(CommandHandler("listwords", AdminHandlers.list_forbidden_words_command, filters=group_filter)) # Corrected termination
    application.add_handler(CommandHandler("togglelinks", AdminHandlers.toggle_links_command, filters=group_filter))
    application.add_handler(CommandHandler("toggleforwards", AdminHandlers.toggle_forwards_command, filters=group_filter))
    application.add_handler(CommandHandler("toggleantiflood", AdminHandlers.toggle_antiflood_command, filters=group_filter))

    # Message Handlers
    # Handles new members and sends welcome message
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, MessageHandlers.handle_new_chat_members))
    # Handles left members and sends farewell message
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, MessageHandlers.handle_left_chat_member))
    # Processes all other text messages in groups for filtering, flood control etc.
    # Ensure it's processed after commands and for non-admin users.
    # The logic to ignore admins is within process_all_group_messages itself.
    application.add_handler(MessageHandler(filters.TEXT & group_filter & (~filters.COMMAND), MessageHandlers.process_all_group_messages))

    # Chat Member Handler (tracks bot's own status in chats)
    application.add_handler(ChatMemberHandler(ChatMemberHandlers.track_bot_status_in_chats, ChatMemberHandler.MY_CHAT_MEMBER))

    logger.info("All handlers registered.")
