import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from telegram_bot.config import settings # Import settings
# Removed: crud, get_db, MessageFilterService, FloodControlService
from telegram_bot.utils.helpers import GeneralHelpers # Updated import
from telegram_bot.core.constants import BotMessages # For any bot messages if needed

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    if not update.effective_user or not update.message: # Ensure message exists for reply
        logger.warning("Start command received without effective user or message.")
        return

    # Use create_user_mention_html for consistency, assuming it returns HTML
    user_mention_html = GeneralHelpers.create_user_mention_html(update.effective_user.id, update.effective_user)
    
    # Updated welcome text to use HTML for the mention
    welcome_text = (
        f"سلام {user_mention_html} عزیز!\n"
        f"به ربات دستیار پیشرفته تلگرام خوش آمدید.\n\n"
        f"قابلیت‌های من:\n"
        f"- Managing group settings\n"
        f"- مدیریت تنظیمات گروه\n"
        f"- فیلتر کردن پیام‌ها (لینک، فروارد، کلمات ممنوعه)\n"
        f"- کنترل سیلاب پیام (Anti-flood)\n"
        f"- و بیشتر!\n\n"
        f"از دستور /help برای مشاهده لیست دستورات استفاده کنید. "
        f"اگر در گروه هستید، مدیران می‌توانند از دستور /settings برای پیکربندی ربات استفاده کنند."
    )
    
    keyboard_buttons = []
    if settings.WEB_APP_URL: # Assuming settings.WEB_APP_URL is correctly loaded
        logger.info(f"Web app URL for start command: {settings.WEB_APP_URL}")
        web_app_button = KeyboardButton("باز کردن برنامه تحت وب", web_app=WebAppInfo(url=settings.WEB_APP_URL))
        keyboard_buttons.append([web_app_button])
    
    reply_markup = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True, one_time_keyboard=True) if keyboard_buttons else None

    try:
        # Send with parse_mode HTML as create_user_mention_html generates HTML
        await update.message.reply_html(welcome_text, reply_markup=reply_markup)
        logger.info(f"Sent start command reply to user {update.effective_user.id} in chat {update.effective_chat.id if update.effective_chat else 'N/A'}")
    except Exception as e:
        logger.error(f"Error sending start command reply: {e}", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    if not update.effective_user or not update.message: # Ensure message exists for reply
        logger.warning("Help command received without effective user or message.")
        return
        
    help_text = (
        "راهنمای دستورات ربات:\n\n"
        " عمومی:\n"
        "/start - نمایش پیام خوشامدگویی (فقط در چت خصوصی)\n"
        "/help - نمایش این راهنما\n"
        "/rules - نمایش قوانین گروه (فقط در گروه)\n"
        "\n دستورات مدیریتی (فقط مدیران گروه):\n"
        "/settings - دسترسی به منوی تنظیمات ربات برای گروه\n"
        "/reload - بارگیری مجدد تنظیمات گروه از پایگاه داده\n"
        "/setrules - تنظیم یا به‌روزرسانی قوانین گروه\n"
        "/setwelcome - تنظیم یا به‌روزرسانی پیام خوشامدگویی\n"
        "/kick @username یا ID - اخراج کاربر\n"
        "/ban @username یا ID - مسدود کردن کاربر\n"
        "/unban @username یا ID - رفع مسدودیت کاربر\n"
        "/mute @username یا ID <زمان> - سکوت کاربر (مثال زمان: 5m, 1h, 2d)\n"
        "/unmute @username یا ID - رفع سکوت کاربر\n"
        "/addword <کلمه> - افزودن کلمه به لیست فیلتر\n"
        "/delword <کلمه> - حذف کلمه از لیست فیلتر\n"
        "/listwords - نمایش لیست کلمات فیلتر شده\n"
        "/togglelinks - فعال/غیرفعال کردن فیلتر لینک\n"
        "/toggleforwards - فعال/غیرفعال کردن فیلتر پیام‌های فروارد شده\n"
        "/toggleantiflood - فعال/غیرفعال کردن سیستم ضد سیلاب\n"
        "\nدر صورت بروز مشکل یا نیاز به راهنمایی بیشتر، با ادمین ربات تماس بگیرید."
    )
    try:
        # Using reply_html as help_text might contain HTML entities if translated from Markdown
        await update.message.reply_html(help_text)
        logger.info(f"Sent help command reply to user {update.effective_user.id} in chat {update.effective_chat.id if update.effective_chat else 'N/A'}")
    except Exception as e:
        logger.error(f"Error sending help command reply: {e}", exc_info=True)

# Removed message_handler, new_member_handler, left_member_handler

if __name__ == "__main__":
    from telegram_bot.core.logging_config import setup_logging # For direct testing
    setup_logging()
    logger.info("General handlers module (start, help) loaded.")
    # To test these handlers, you would typically use the ApplicationBuilder from main.py
    pass
