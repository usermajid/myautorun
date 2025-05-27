"""
ماژول تنظیمات و راه‌اندازی اولیه ربات تلگرام.

این ماژول شامل توابعی برای انجام عملیات پس از ایجاد شیء `Application`
(مانند تنظیم دستورات ربات) و همچنین ثبت تمامی handler های برنامه
(شامل دستورات، پیام‌ها، وضعیت اعضا و خطاها) می‌باشد.
"""
from telegram import BotCommand, MenuButtonCommands
from telegram.ext import Application, CommandHandler, MessageHandler, ChatMemberHandler, filters, PicklePersistence

# Import handler classes
from telegram_bot.handlers.general import GeneralHandlers
from telegram_bot.handlers.admin import (
    AdminHandlers, 
    AdminConversationState,
    settings_callback_handler, 
    received_welcome_message,
    received_farewell_message, 
    received_rules_text, 
    received_max_messages,
    cancel_settings_conversation, 
    forbidden_words_menu_callback,
    received_forbidden_word_to_add, 
    received_forbidden_word_to_remove
)
from telegram_bot.handlers.message import MessageHandlers
from telegram_bot.handlers.chat_member import ChatMemberHandlers
from telegram_bot.handlers.error import global_error_handler # Direct import of the function
from telegram.ext import ConversationHandler, CallbackQueryHandler # Added for ConversationHandler

# Import settings if needed for persistence or other setup
from telegram_bot.config import settings
import logging

logger = logging.getLogger(__name__)

async def post_bot_initialization(application: Application) -> None:
    """
    انجام تنظیمات پس از مقداردهی اولیه شیء Application ربات.

    این تابع موارد زیر را انجام می‌دهد:
    - تعریف لیست دستورات ربات (BotCommand) که در منوی تلگرام نمایش داده می‌شوند.
    - ارسال این دستورات به سرور تلگرام با استفاده از `application.bot.set_my_commands`.
    - تنظیم دکمه منوی پیش‌فرض ربات در چت‌ها.

    Args:
        application: شیء Application ربات.
    """
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
    """
    ثبت تمامی handler های ربات به شیء Application.

    این تابع handler های زیر را ثبت می‌کند:
    - کنترل‌کننده خطای عمومی (global_error_handler).
    - Handler های عمومی (مانند /start, /help, /rules).
    - Handler های دستورات ادمین (مانند /setrules, /kick, /ban, و دستورات مربوط به فیلترها).
    - Handler های پیام (مانند خوشامدگویی به اعضای جدید، بدرقه اعضای خارج شده، پردازش پیام‌های گروهی برای فیلترینگ و ضد سیلاب).
    - Handler مربوط به تغییرات وضعیت عضویت خود ربات در گروه‌ها.

    Args:
        application: شیء Application ربات.
    """
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

    # Settings Conversation Handler
    settings_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("settings", AdminHandlers.settings_command, filters=filters.ChatType.GROUPS)],
        states={
            AdminConversationState.SELECTING_SETTING: [
                CallbackQueryHandler(settings_callback_handler, pattern='^settings_')
            ],
            AdminConversationState.EDITING_WELCOME_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_welcome_message)
            ],
            AdminConversationState.EDITING_FAREWELL_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_farewell_message)
            ],
            AdminConversationState.EDITING_RULES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_rules_text)
            ],
            AdminConversationState.SETTING_MAX_MESSAGES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_max_messages)
            ],
            AdminConversationState.SELECTING_ACTION: [ # State for forbidden words menu
                CallbackQueryHandler(forbidden_words_menu_callback, pattern='^fw_')
            ],
            AdminConversationState.ADDING_FORBIDDEN_WORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_forbidden_word_to_add)
            ],
            AdminConversationState.REMOVING_FORBIDDEN_WORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, received_forbidden_word_to_remove)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_settings_conversation),
            CallbackQueryHandler(cancel_settings_conversation, pattern='^settings_close_')
        ],
        # per_user=True, per_chat=False # Default is per_user=True, per_chat=True
        name="settings_conversation",
        persistent=False 
    )
    application.add_handler(settings_conv_handler)

    logger.info("All handlers registered.")
