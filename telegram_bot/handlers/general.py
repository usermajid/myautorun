import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import ContextTypes
from telegram_bot.database import crud
from telegram_bot.database.engine import get_db
from telegram_bot.services.message_filter import MessageFilterService
from telegram_bot.services.flood_control import FloodControlService
from telegram_bot.config import settings # Import settings
from telegram_bot.utils.helpers import get_user_mention # For welcome/farewell messages

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    if not update.effective_user or not update.effective_chat:
        logger.warning("Start command received without effective user or chat.")
        return

    user_mention = get_user_mention(update.effective_user)
    welcome_text = (
        f"Hello {user_mention}! I am your new Telegram Bot Assistant.\n\n"
        f"I can help you with:\n"
        f"- Managing group settings\n"
        f"- Filtering messages (links, forwards, forbidden words)\n"
        f"- Flood control\n"
        f"- And more!\n\n"
        f"Use /help to see available commands. If this is a group, admins can use /settings to configure me."
    )
    
    # Adding a button for Web App (if configured)
    keyboard = []
    if settings.WEB_APP_URL:
        logger.info(f"Web app URL found: {settings.WEB_APP_URL}")
        web_app_button = KeyboardButton("Open Web App", web_app=WebAppInfo(url=settings.WEB_APP_URL))
        keyboard.append([web_app_button])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True) if keyboard else None

    try:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='MarkdownV2')
        logger.info(f"Sent start command reply to user {update.effective_user.id} in chat {update.effective_chat.id}")
    except Exception as e:
        logger.error(f"Error sending start command reply: {e}", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    if not update.effective_user or not update.effective_chat:
        logger.warning("Help command received without effective user or chat.")
        return
        
    help_text = (
        "Here are the available commands:\n"
        "/start - Welcome message\n"
        "/help - Shows this help message\n"
        # Group specific commands (mostly for admins)
        "\n*Admin Commands (in groups):*\n"
        "/settings - Configure bot settings for this group (e.g., welcome message, link filtering)\n"
        "/reload - Reloads settings for the current group (admins only)\n"
        "/addword <word> - Add a word to the forbidden list\n"
        "/removeword <word> - Remove a word from the forbidden list\n"
        "/listwords - List all forbidden words for this group\n"
        # "/kick <user_mention_or_id> [reason] - Kick a user\n" # Example for future
        # "/ban <user_mention_or_id> [reason] - Ban a user\n"   # Example for future
        "\nIf you have any issues or feature requests, please contact the bot admin."
    )
    try:
        await update.message.reply_text(help_text, parse_mode='Markdown') # Using Markdown for simplicity here
        logger.info(f"Sent help command reply to user {update.effective_user.id} in chat {update.effective_chat.id}")
    except Exception as e:
        logger.error(f"Error sending help command reply: {e}", exc_info=True)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles general messages: checks for flood, filters messages."""
    if not update.message or not update.effective_chat: # Ignore updates without a message or chat
        logger.debug("Message handler: No message or effective_chat found in update.")
        return

    # Flood Control Check
    # Initialize FloodControlService with the current update and context
    flood_service = FloodControlService(update, context)
    if await flood_service.check_and_handle_flood():
        logger.info(f"Flood detected and handled for user {update.message.from_user.id if update.message.from_user else 'Unknown'} in chat {update.effective_chat.id}. No further processing.")
        return # Stop processing if flood detected and handled

    # Message Filtering
    # Initialize MessageFilterService
    filter_service = MessageFilterService(update, context)
    if await filter_service.filter_message():
        logger.info(f"Message from user {update.message.from_user.id if update.message.from_user else 'Unknown'} in chat {update.effective_chat.id} was filtered. No further processing.")
        return # Stop processing if message was filtered (e.g., deleted)

    # If the message is "hello", reply with "world" (example of simple interaction)
    if update.message.text and update.message.text.lower() == 'hello':
        try:
            await update.message.reply_text('World!')
            logger.info(f"Replied 'World!' to 'hello' from user {update.message.from_user.id if update.message.from_user else 'Unknown'} in chat {update.effective_chat.id}")
        except Exception as e:
            logger.error(f"Error replying 'World!' to 'hello': {e}", exc_info=True)
    
    # Add any other general message processing logic here.
    # For example, if you want the bot to respond to specific keywords or phrases.

    logger.debug(f"Message from {update.message.from_user.id if update.message.from_user else 'Unknown'} in chat {update.effective_chat.id} processed by general message_handler.")


async def new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles new members joining the group."""
    if not update.message or not update.message.new_chat_members or not update.effective_chat:
        logger.debug("New member handler: No new members or effective_chat.")
        return

    db = next(get_db())
    try:
        group_settings = crud.get_or_create_group_setting(db, update.effective_chat.id)
        if group_settings and group_settings.welcome_message:
            for member in update.message.new_chat_members:
                if member.is_bot: # Optional: Don't send welcome message to bots
                    logger.info(f"Bot {member.username or member.id} joined chat {update.effective_chat.id}. Skipping welcome message.")
                    continue
                
                user_mention = get_user_mention(member) # Use helper for consistent mention
                welcome_msg = group_settings.welcome_message.format(
                    user_mention=user_mention,
                    user_name=member.full_name, # Corrected from first_name to full_name for more flexibility
                    group_name=update.effective_chat.title or "this group"
                )
                try:
                    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')
                    logger.info(f"Sent welcome message to new member {member.id} in chat {update.effective_chat.id}")
                except Exception as e:
                    logger.error(f"Error sending welcome message to {member.id}: {e}", exc_info=True)
    finally:
        db.close()


async def left_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles members leaving or being kicked from the group."""
    if not update.message or not update.message.left_chat_member or not update.effective_chat:
        logger.debug("Left member handler: No left member or effective_chat.")
        return

    db = next(get_db())
    try:
        group_settings = crud.get_or_create_group_setting(db, update.effective_chat.id)
        if group_settings and group_settings.farewell_message:
            member = update.message.left_chat_member
            if member.is_bot: # Optional: Don't send farewell message for bots
                logger.info(f"Bot {member.username or member.id} left chat {update.effective_chat.id}. Skipping farewell message.")
                return

            user_mention = get_user_mention(member) # Use helper
            farewell_msg = group_settings.farewell_message.format(
                user_mention=user_mention, # Using consistent mention
                user_name=member.full_name, # Corrected from first_name to full_name
                group_name=update.effective_chat.title or "this group"
            )
            try:
                # Sending to the chat. If the user has left, they won't see it, but group members will.
                await context.bot.send_message(chat_id=update.effective_chat.id, text=farewell_msg, parse_mode='MarkdownV2')
                logger.info(f"Sent farewell message for member {member.id} in chat {update.effective_chat.id}")
            except Exception as e:
                logger.error(f"Error sending farewell message for {member.id}: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    # This part is for testing or direct execution, which is unlikely for handlers.
    from telegram_bot.core.logging_config import setup_logging
    setup_logging() # Configure logging
    logger.info("General handlers module loaded. Contains handlers for start, help, messages, new/left members.")
    # To test these handlers, you would typically use the ApplicationBuilder and run the bot,
    # then interact with it using a Telegram client.
    pass
