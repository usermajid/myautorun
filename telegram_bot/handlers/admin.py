import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram_bot.database import crud
from telegram_bot.database.engine import get_db
from telegram_bot.services.permissions import require_admin_privileges, is_user_admin_or_owner # For decorators and checks
from telegram_bot.database.models import GroupSetting # For type hinting
from telegram_bot.database.engine import AsyncSessionFactory # For async operations
from telegram_bot.database.crud import GroupSettingCRUD, ForbiddenWordCRUD # Use async CRUD
from telegram_bot.core.constants import BotMessages, BotSettings # For message templates
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Conversation states for /settings command - These might need to be class attributes or handled differently if settings becomes a class
# For now, keeping them module-level as they are tied to ConversationHandler states
(SELECTING_ACTION, SELECTING_SETTING, CHANGING_SETTING, ADDING_FORBIDDEN_WORD, REMOVING_FORBIDDEN_WORD, LISTING_FORBIDDEN_WORDS, TOGGLING_BOOLEAN, EDITING_WELCOME_MESSAGE, EDITING_FAREWELL_MESSAGE, EDITING_RULES, SETTING_MAX_MESSAGES) = range(11)


class AdminHandlers:
    """
    Encapsulates all admin command handlers and related helper methods.
    """

    # --- Helper Functions (now part of the class or refactored) ---
    @staticmethod
    def get_settings_keyboard(group_id: int, settings: GroupSetting) -> InlineKeyboardMarkup:
        """Generates the settings keyboard for the given group_id, reflecting current settings."""
        keyboard = [
            [InlineKeyboardButton(f"پیام خوشامدگویی ({'فعال' if settings.welcome_message_active else 'غیرفعال'})", callback_data=f"settings_toggle_welcome_active_{group_id}")],
            [InlineKeyboardButton("ویرایش پیام خوشامدگویی", callback_data=f"settings_edit_welcome_message_{group_id}")],
            [InlineKeyboardButton(f"پیام بدرقه ({'فعال' if settings.farewell_message_active else 'غیرفعال'})", callback_data=f"settings_toggle_farewell_active_{group_id}")],
            [InlineKeyboardButton("ویرایش پیام بدرقه", callback_data=f"settings_edit_farewell_message_{group_id}")],
            [InlineKeyboardButton("قوانین گروه", callback_data=f"settings_edit_rules_{group_id}")],
            [InlineKeyboardButton(f"فیلتر لینک ({'فعال' if settings.filter_links_active else 'غیرفعال'})", callback_data=f"settings_toggle_filter_links_active_{group_id}")],
            [InlineKeyboardButton(f"فیلتر فروارد ({'فعال' if settings.filter_forwards_active else 'غیرفعال'})", callback_data=f"settings_toggle_filter_forwards_active_{group_id}")],
            [InlineKeyboardButton(f"سیستم ضد سیلاب ({'فعال' if settings.anti_flood_active else 'غیرفعال'})", callback_data=f"settings_toggle_anti_flood_active_{group_id}")],
            [InlineKeyboardButton(f"حداکثر پیام در دقیقه (ضد سیلاب): {settings.max_messages_per_minute}", callback_data=f"settings_set_max_messages_{group_id}")],
            [InlineKeyboardButton("مدیریت کلمات ممنوعه", callback_data=f"settings_manage_forbidden_words_{group_id}")],
            [InlineKeyboardButton("بستن منو", callback_data=f"settings_close_{group_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_forbidden_words_menu_keyboard(group_id: int) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("افزودن کلمه ممنوعه", callback_data=f"fw_add_{group_id}")],
            [InlineKeyboardButton("حذف کلمه ممنوعه", callback_data=f"fw_remove_{group_id}")],
            [InlineKeyboardButton("نمایش لیست کلمات ممنوعه", callback_data=f"fw_list_{group_id}")],
            [InlineKeyboardButton("بازگشت به تنظیمات اصلی", callback_data=f"fw_back_to_settings_{group_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)

    # --- Main Command Handlers (now static methods) ---
    @staticmethod
    @require_admin_privileges
    async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if not update.effective_chat or not update.effective_user:
            return ConversationHandler.END

        group_id = update.effective_chat.id
        logger.info(f"Admin {update.effective_user.id} initiated /settings for group {group_id}.")

        async with AsyncSessionFactory() as session:
            group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown Group")
            if not group_settings:
                await update.message.reply_text("خطا در دسترسی به تنظیمات گروه. لطفاً دوباره تلاش کنید.")
                return ConversationHandler.END

        keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
        await update.message.reply_text("⚙️ تنظیمات گروه ⚙️\n\nگزینه‌ای را برای مدیریت انتخاب کنید:", reply_markup=keyboard)
        return SELECTING_SETTING

    @staticmethod
    @require_admin_privileges
    async def reload_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.effective_user: return

        group_id = update.effective_chat.id
        logger.info(f"Admin {update.effective_user.id} initiated /reload for group {group_id}.")
        async with AsyncSessionFactory() as session:
            settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown Group")
            if settings:
                await update.message.reply_text("تنظیمات گروه از پایگاه داده مجدداً بارگیری شد.")
            else:
                await update.message.reply_text("خطا در بارگیری مجدد تنظیمات.")

    @staticmethod
    @require_admin_privileges
    async def add_forbidden_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.effective_user or not context.args:
            await update.message.reply_text("استفاده: /addword <کلمه_ممنوعه>")
            return

        group_id = update.effective_chat.id
        word_to_add = " ".join(context.args).strip().lower()
        if not word_to_add:
            await update.message.reply_text("لطفاً کلمه‌ای را برای ممنوع کردن مشخص کنید.")
            return

        async with AsyncSessionFactory() as session:
            added_word = await ForbiddenWordCRUD.create(session, group_id, word_to_add)
            if added_word:
                await update.message.reply_text(f"کلمه '{added_word.word}' به لیست کلمات ممنوعه اضافه شد.")
            else:
                await update.message.reply_text(f"کلمه '{word_to_add}' ممکن است از قبل ممنوع باشد یا خطایی رخ داده است.")

    @staticmethod
    @require_admin_privileges
    async def remove_forbidden_word_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.effective_user or not context.args:
            await update.message.reply_text("استفاده: /removeword <کلمه_مجاز>")
            return

        group_id = update.effective_chat.id
        word_to_remove = " ".join(context.args).strip().lower()
        if not word_to_remove:
            await update.message.reply_text("لطفاً کلمه‌ای را برای مجاز کردن مشخص کنید.")
            return

        async with AsyncSessionFactory() as session:
            if await ForbiddenWordCRUD.delete(session, group_id, word_to_remove):
                await update.message.reply_text(f"کلمه '{word_to_remove}' از لیست کلمات ممنوعه حذف شد.")
            else:
                await update.message.reply_text(f"کلمه '{word_to_remove}' در لیست ممنوعه یافت نشد.")

    @staticmethod
    @require_admin_privileges
    async def list_forbidden_words_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.effective_user: return

        group_id = update.effective_chat.id
        async with AsyncSessionFactory() as session:
            words = await ForbiddenWordCRUD.get_all_words_for_group(session, group_id) # Assuming this method exists
            if not words:
                await update.message.reply_text("هیچ کلمه ممنوعه‌ای برای این گروه تنظیم نشده است.")
            else:
                message = "کلمات ممنوعه در این گروه:\n" + "\n".join(f"- `{word}`" for word in words)
                await update.message.reply_text(message, parse_mode='MarkdownV2')

    @staticmethod
    @require_admin_privileges
    async def _toggle_filter_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, setting_type: str, db_field_name: str, setting_name_fa: str) -> None:
        """Helper function to toggle a boolean filter setting."""
        if not update.effective_chat or not update.message:
            return

        group_id = update.effective_chat.id
        chat_title = update.effective_chat.title or "گروه"
        current_status_text = ""
        new_status = False

        async with AsyncSessionFactory() as session:
            try:
                group_settings = await GroupSettingCRUD.get_or_create(session, group_id, chat_title)
                current_status = getattr(group_settings, db_field_name)
                new_status = not current_status
                await GroupSettingCRUD.update(session, group_id, **{db_field_name: new_status})
                await session.commit()
                current_status_text = "فعال" if new_status else "غیرفعال"
                reply_text = f"{setting_name_fa} با موفقیت {current_status_text} شد."
                logger.info(f"Setting '{db_field_name}' for group {group_id} toggled to {new_status} by admin {update.effective_user.id if update.effective_user else 'Unknown'}.")
            except SQLAlchemyError as e:
                logger.error(f"Database error while toggling '{db_field_name}' for group {group_id}: {e}", exc_info=True)
                reply_text = BotMessages.DB_ERROR_MESSAGE
                await session.rollback()
            except Exception as e:
                logger.error(f"Unexpected error while toggling '{db_field_name}' for group {group_id}: {e}", exc_info=True)
                reply_text = BotMessages.GENERIC_ERROR_MESSAGE
                await session.rollback() # Ensure rollback on unexpected errors too

        await update.message.reply_text(reply_text)

    @staticmethod
    @require_admin_privileges
    async def toggle_links_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await AdminHandlers._toggle_filter_setting(update, context, "links", "filter_links_active", "فیلتر لینک")

    @staticmethod
    @require_admin_privileges
    async def toggle_forwards_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await AdminHandlers._toggle_filter_setting(update, context, "forwards", "filter_forwards_active", "فیلتر پیام‌های فروارد شده")

    @staticmethod
    @require_admin_privileges
    async def toggle_antiflood_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await AdminHandlers._toggle_filter_setting(update, context, "antiflood", "anti_flood_active", "سیستم ضد سیلاب")


# --- Conversation Handler Callbacks (remain module-level or need careful integration if settings becomes a class) ---
# For simplicity, these remain module-level functions that interact with CRUD operations.
# They might need access to static methods from AdminHandlers if helper functions are moved there exclusively.

async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or not update.effective_chat or not update.effective_user:
        return ConversationHandler.END

    group_id = update.effective_chat.id
    action_parts = query.data.split('_')
    action_prefix = action_parts[0]
    main_action = action_parts[1] # e.g., "toggle", "edit", "manage", "set"
    
    # Example: settings_toggle_welcome_active_12345
    #          settings_edit_welcome_message_12345
    #          settings_manage_forbidden_words_12345
    #          settings_close_12345

    if main_action == "close":
        await query.edit_message_text("منوی تنظیمات بسته شد.")
        return ConversationHandler.END

    async with AsyncSessionFactory() as session:
        group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown")

        if main_action == "toggle":
            setting_key = action_parts[2] # e.g., "welcome" or "filter_links_active"
            bool_field_name = setting_key # This needs to map to actual GroupSetting field names
            
            # This is a simplified mapping. You'll need to map callback data to actual model fields.
            # E.g., 'welcome_active' maps to 'welcome_message_active'
            field_map = {
                "welcome": "welcome_message_active",
                "farewell": "farewell_message_active",
                "filter_links": "filter_links_active",
                "filter_forwards": "filter_forwards_active",
                "anti_flood": "anti_flood_active",
            }
            actual_db_field = field_map.get(setting_key, None)

            if actual_db_field:
                current_value = getattr(group_settings, actual_db_field)
                new_value = not current_value
                await GroupSettingCRUD.update(session, group_id, **{actual_db_field: new_value})
                await session.commit()
                logger.info(f"Toggled {actual_db_field} to {new_value} for group {group_id}")
            else:
                logger.warning(f"Unknown toggle setting key: {setting_key} from callback {query.data}")
                await query.edit_message_text("خطا: تنظیم ناشناخته.")
                # Refresh settings and keyboard
                group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown") # Re-fetch
                keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
                await query.edit_message_text("⚙️ تنظیمات گروه ⚙️", reply_markup=keyboard)
                return SELECTING_SETTING


        elif main_action == "edit":
            setting_to_edit = action_parts[2] # e.g., "welcome", "farewell", "rules"
            context.user_data['setting_to_edit'] = setting_to_edit
            context.user_data['group_id_for_edit'] = group_id
            
            prompt_message = ""
            next_state = -1
            if setting_to_edit == "welcome":
                prompt_message = BotMessages.WELCOME_MESSAGE_PROMPT
                next_state = EDITING_WELCOME_MESSAGE
            elif setting_to_edit == "farewell":
                prompt_message = BotMessages.FAREWELL_MESSAGE_PROMPT
                next_state = EDITING_FAREWELL_MESSAGE
            elif setting_to_edit == "rules":
                prompt_message = BotMessages.RULES_PROMPT
                next_state = EDITING_RULES
            else:
                await query.edit_message_text("خطا: بخش ویرایش ناشناخته.")
                # Refresh keyboard
                group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown") # Re-fetch
                keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
                await query.edit_message_text("⚙️ تنظیمات گروه ⚙️", reply_markup=keyboard)
                return SELECTING_SETTING

            await query.edit_message_text(prompt_message)
            return next_state

        elif main_action == "manage" and action_parts[2] == "forbidden_words":
            keyboard = AdminHandlers.get_forbidden_words_menu_keyboard(group_id)
            await query.edit_message_text("จัดการ کلمات ممنوعه:", reply_markup=keyboard)
            return SELECTING_ACTION # State for FW management

        elif main_action == "set" and action_parts[2] == "max_messages": # settings_set_max_messages_GROUPID
            context.user_data['setting_to_edit'] = 'max_messages_per_minute'
            context.user_data['group_id_for_edit'] = group_id
            await query.edit_message_text(BotMessages.MAX_MESSAGES_PROMPT)
            return SETTING_MAX_MESSAGES
            
        # Refresh settings and keyboard after any action
        group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown") # Re-fetch
        keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
        await query.edit_message_text("⚙️ تنظیمات گروه ⚙️", reply_markup=keyboard)
        return SELECTING_SETTING


async def received_new_setting_text_value(update: Update, context: ContextTypes.DEFAULT_TYPE, state_to_return_to: int) -> int:
    if not update.message or not update.message.text or not context.user_data or not update.effective_user:
        await update.message.reply_text("پردازش تنظیمات جدید با مشکل مواجه شد. لطفاً مجدداً از /settings شروع کنید.")
        return ConversationHandler.END

    new_value = update.message.text
    setting_key = context.user_data.get('setting_to_edit')
    group_id = context.user_data.get('group_id_for_edit')

    if not setting_key or group_id is None or group_id != update.effective_chat.id:
        await update.message.reply_text("خطا: زمینه تنظیمات نامعتبر است. لطفاً از /settings در گروه صحیح استفاده کنید.")
        context.user_data.clear()
        return ConversationHandler.END

    update_kwargs = {}
    success_message = ""

    if setting_key == 'welcome_message':
        update_kwargs['welcome_message'] = new_value
        success_message = "پیام خوشامدگویی با موفقیت به‌روز شد."
    elif setting_key == 'farewell_message':
        update_kwargs['farewell_message'] = new_value
        success_message = "پیام بدرقه با موفقیت به‌روز شد."
    elif setting_key == 'rules':
        update_kwargs['rules'] = new_value
        success_message = "قوانین گروه با موفقیت به‌روز شد."
    elif setting_key == 'max_messages_per_minute':
        try:
            max_val = int(new_value)
            if not (1 <= max_val <= 60): # Example range
                await update.message.reply_text("مقدار نامعتبر. لطفاً عددی بین ۱ تا ۶۰ وارد کنید.")
                return state_to_return_to # Stay in current state
            update_kwargs['max_messages_per_minute'] = max_val
            success_message = f"حداکثر پیام در دقیقه به {max_val} تغییر یافت."
        except ValueError:
            await update.message.reply_text("ورودی نامعتبر. لطفاً یک عدد صحیح وارد کنید.")
            return state_to_return_to # Stay in current state for re-entry
    else:
        await update.message.reply_text(f"خطا: تنظیم ناشناخته '{setting_key}'.")
        context.user_data.clear()
        # Show main settings menu again
        async with AsyncSessionFactory() as session:
            group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown")
            keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
            await update.message.reply_text("⚙️ تنظیمات گروه ⚙️", reply_markup=keyboard)
        return SELECTING_SETTING


    async with AsyncSessionFactory() as session:
        try:
            await GroupSettingCRUD.update(session, group_id, **update_kwargs)
            await session.commit()
            await update.message.reply_text(success_message)
            logger.info(f"Setting '{setting_key}' for group {group_id} updated to '{new_value}' by admin {update.effective_user.id}.")
        except SQLAlchemyError as e:
            logger.error(f"DB error updating setting {setting_key} for group {group_id}: {e}", exc_info=True)
            await update.message.reply_text(BotMessages.DB_ERROR_MESSAGE)
            await session.rollback()
        except Exception as e:
            logger.error(f"Unexpected error updating setting {setting_key} for group {group_id}: {e}", exc_info=True)
            await update.message.reply_text(BotMessages.GENERIC_ERROR_MESSAGE)
            await session.rollback()
        
        context.user_data.clear()
        group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown")
        keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
        await update.message.reply_text("⚙️ تنظیمات گروه ⚙️", reply_markup=keyboard)
        return SELECTING_SETTING

# Specific handlers for each text input state, calling the generic one
async def received_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await received_new_setting_text_value(update, context, EDITING_WELCOME_MESSAGE)
async def received_farewell_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await received_new_setting_text_value(update, context, EDITING_FAREWELL_MESSAGE)
async def received_rules_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await received_new_setting_text_value(update, context, EDITING_RULES)
async def received_max_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await received_new_setting_text_value(update, context, SETTING_MAX_MESSAGES)


async def cancel_settings_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the ongoing settings conversation."""
    reply_text = "عملیات ویرایش تنظیمات لغو شد."
    if update.message:
        await update.message.reply_text(reply_text)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(reply_text)
    
    logger.info(f"Settings conversation cancelled by user {update.effective_user.id if update.effective_user else 'Unknown'}.")
    context.user_data.clear()
    return ConversationHandler.END


async def forbidden_words_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not query.data or not update.effective_chat or not update.effective_user:
        return SELECTING_SETTING

    group_id = update.effective_chat.id
    action = query.data.split('_')[1] # fw_add, fw_remove, fw_list, fw_back

    context.user_data['group_id_for_fw'] = group_id

    if action == "add":
        await query.edit_message_text("لطفاً کلمه یا عبارت ممنوعه جدید را ارسال کنید.")
        return ADDING_FORBIDDEN_WORD
    elif action == "remove":
        await query.edit_message_text("لطفاً کلمه یا عبارتی که می‌خواهید از لیست ممنوعه حذف شود را ارسال کنید.")
        return REMOVING_FORBIDDEN_WORD
    elif action == "list":
        async with AsyncSessionFactory() as session:
            words = await ForbiddenWordCRUD.get_all_words_for_group(session, group_id)
            if not words:
                message_text = "لیست کلمات ممنوعه خالی است."
            else:
                message_text = "کلمات ممنوعه فعلی:\n" + "\n".join(f"- `{word}`" for word in words)
            keyboard = AdminHandlers.get_forbidden_words_menu_keyboard(group_id) # Show menu again
            await query.edit_message_text(message_text, parse_mode='MarkdownV2', reply_markup=keyboard)
        return SELECTING_ACTION # Stay in FW menu
    elif action == "back":
        async with AsyncSessionFactory() as session:
            group_settings = await GroupSettingCRUD.get_or_create(session, group_id, update.effective_chat.title or "Unknown")
            keyboard = AdminHandlers.get_settings_keyboard(group_id, group_settings)
            await query.edit_message_text("⚙️ تنظیمات گروه ⚙️", reply_markup=keyboard)
        return SELECTING_SETTING
    else:
        await query.edit_message_text("دستور نامعتبر.")
        return SELECTING_ACTION


async def received_forbidden_word_to_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text or not context.user_data or not update.effective_user:
        await update.message.reply_text("پردازش با مشکل مواجه شد. لطفاً مجدداً از /settings شروع کنید.")
        return ConversationHandler.END

    word_to_add = update.message.text.strip().lower()
    group_id = context.user_data.get('group_id_for_fw')

    if not group_id or group_id != update.effective_chat.id:
        await update.message.reply_text("خطا در زمینه. لطفاً از /settings در گروه صحیح استفاده کنید.")
        context.user_data.clear()
        return ConversationHandler.END
    
    if not word_to_add:
        await update.message.reply_text("کلمه‌ای وارد نشده است. لطفاً کلمه را برای ممنوع کردن ارسال کنید.")
        return ADDING_FORBIDDEN_WORD

    async with AsyncSessionFactory() as session:
        added = await ForbiddenWordCRUD.create(session, group_id, word_to_add)
        if added:
            await update.message.reply_text(f"کلمه '{word_to_add}' به لیست ممنوعه اضافه شد.")
        else:
            await update.message.reply_text(f"کلمه '{word_to_add}' از قبل در لیست وجود دارد یا خطایی رخ داده.")
        
        keyboard = AdminHandlers.get_forbidden_words_menu_keyboard(group_id)
        await update.message.reply_text("مدیریت کلمات ممنوعه:", reply_markup=keyboard)
        return SELECTING_ACTION


async def received_forbidden_word_to_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text or not context.user_data or not update.effective_user:
        await update.message.reply_text("پردازش با مشکل مواجه شد. لطفاً مجدداً از /settings شروع کنید.")
        return ConversationHandler.END

    word_to_remove = update.message.text.strip().lower()
    group_id = context.user_data.get('group_id_for_fw')

    if not group_id or group_id != update.effective_chat.id:
        await update.message.reply_text("خطا در زمینه. لطفاً از /settings در گروه صحیح استفاده کنید.")
        context.user_data.clear()
        return ConversationHandler.END

    if not word_to_remove:
        await update.message.reply_text("کلمه‌ای وارد نشده است. لطفاً کلمه را برای حذف ارسال کنید.")
        return REMOVING_FORBIDDEN_WORD

    async with AsyncSessionFactory() as session:
        deleted = await ForbiddenWordCRUD.delete(session, group_id, word_to_remove)
        if deleted:
            await update.message.reply_text(f"کلمه '{word_to_remove}' از لیست ممنوعه حذف شد.")
        else:
            await update.message.reply_text(f"کلمه '{word_to_remove}' در لیست ممنوعه یافت نشد.")

        keyboard = AdminHandlers.get_forbidden_words_menu_keyboard(group_id)
        await update.message.reply_text("مدیریت کلمات ممنوعه:", reply_markup=keyboard)
        return SELECTING_ACTION


if __name__ == "__main__":
    from telegram_bot.core.logging_config import setup_logging
    setup_logging()
    logger.info("Admin handlers module loaded. Contains handlers for /settings, /reload, and forbidden words management.")
    # ConversationHandler setup example would be in main.py
    pass
# This is the new content for the AdminHandlers class and related conversation handlers.
# It includes the requested toggle_forwards_command and toggle_antiflood_command.
# Note: This is a significant refactor of the original admin.py structure.
# The original file was mostly function-based, this introduces a class AdminHandlers.
# Conversation states and handlers are kept module-level for now, but might need
# further integration if the settings conversation itself becomes a class method.
pass # Placeholder for the actual diff content
