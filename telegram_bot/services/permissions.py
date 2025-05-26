import logging
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from typing import Optional, Dict, Any
from telegram_bot.config import settings # Import settings
import logging
import time

logger = logging.getLogger(__name__)

# Cache for bot permissions to reduce API calls
# Structure: {chat_id: {"timestamp": float, "permissions": ChatMember}}
_bot_permissions_cache: Dict[int, Dict[str, Any]] = {}
CACHE_EXPIRY_SECONDS = 300 # 5 minutes, adjust as needed


# Permission levels (example, can be expanded) - These might be less needed if directly using ChatMember statuses
ADMIN_LEVEL = ChatMemberStatus.ADMINISTRATOR
OWNER_LEVEL = ChatMemberStatus.OWNER # 'creator' is ChatMemberStatus.OWNER

async def get_user_status_in_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[str]:
    """Gets the status of a user in the chat (e.g., member, administrator, owner)."""
    if not update.effective_chat: # Should ideally always have effective_chat for group operations
        logger.warning("get_user_status_in_chat called without effective_chat.")
        return None
    try:
        # Ensure user_id is an int as expected by get_chat_member
        member_user_id = int(user_id) 
        chat_member = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=member_user_id)
        logger.debug(f"User {member_user_id} status in chat {update.effective_chat.id}: {chat_member.status}")
        return chat_member.status
    except Exception as e:
        logger.error(f"Error getting chat member status for user {user_id} in chat {update.effective_chat.id}: {e}", exc_info=True)
        return None

async def is_user_admin_or_owner(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_to_check: Optional[int] = None) -> bool:
    """Checks if the user (or message sender if user_id_to_check is None) is an admin or owner of the chat."""
    
    target_user_id = user_id_to_check
    if target_user_id is None:
        if not update.effective_user: # Should always have effective_user if called from a user action
            logger.warning("is_user_admin_or_owner called without effective_user and no user_id_to_check provided.")
            return False
        target_user_id = update.effective_user.id
    
    # Ensure target_user_id is an integer
    try:
        target_user_id = int(target_user_id)
    except (ValueError, TypeError):
        logger.warning(f"Invalid user_id_to_check: {target_user_id}. Must be an integer.")
        return False

    # Check against settings.OWNER_IDS first
    if target_user_id in settings.OWNER_IDS:
        logger.info(f"User {target_user_id} is a bot owner (super admin). Granting admin/owner privileges.")
        return True

    if not update.effective_chat: # Required for get_chat_member
        logger.warning("is_user_admin_or_owner called without effective_chat context.")
        return False

    status = await get_user_status_in_chat(update, context, target_user_id) # Pass target_user_id here
    
    # Simplified status check
    is_admin = status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    
    if is_admin:
        logger.info(f"User {target_user_id} is an admin/owner in chat {update.effective_chat.id} (status: {status}).")
    else:
        logger.debug(f"User {target_user_id} is NOT an admin/owner in chat {update.effective_chat.id} (status: {status}).")
    return is_admin


class PermissionService: # Class-based structure for better organization
    @staticmethod
    async def get_bot_permissions(chat_id: int, context: ContextTypes.DEFAULT_TYPE, force_refresh: bool = False) -> Optional[ChatMember]:
        """Gets the bot's own permissions in a chat, with caching."""
        now = time.time()
        if not force_refresh and chat_id in _bot_permissions_cache:
            cached_data = _bot_permissions_cache[chat_id]
            if now - cached_data["timestamp"] < CACHE_EXPIRY_SECONDS:
                logger.debug(f"Using cached bot permissions for chat {chat_id}")
                return cached_data["permissions"]

        try:
            bot_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=context.bot.id)
            _bot_permissions_cache[chat_id] = {"timestamp": now, "permissions": bot_member}
            logger.debug(f"Fetched and cached bot permissions for chat {chat_id}: {bot_member.status}")
            return bot_member
        except Exception as e:
            logger.error(f"Error getting bot's chat member info in chat {chat_id}: {e}", exc_info=True)
            return None

    @staticmethod
    async def bot_is_admin(chat_id: int, context: ContextTypes.DEFAULT_TYPE, force_refresh: bool = False) -> bool:
        """Checks if the bot itself is an administrator in the current chat."""
        bot_member = await PermissionService.get_bot_permissions(chat_id, context, force_refresh)
        if bot_member:
            is_admin = bot_member.status == ChatMemberStatus.ADMINISTRATOR
            if is_admin:
                logger.info(f"Bot is an admin in chat {chat_id}.")
            else:
                logger.info(f"Bot is NOT an admin in chat {chat_id} (status: {bot_member.status}).")
            return is_admin
        return False
    
    @staticmethod
    async def can_bot_delete_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        bot_member = await PermissionService.get_bot_permissions(chat_id, context)
        if bot_member and isinstance(bot_member, ChatMember.ADMINISTRATOR): # Ensure it's the Administrator type
            can_delete = bot_member.can_delete_messages
            logger.debug(f"Bot can_delete_messages in chat {chat_id}: {can_delete}")
            return bool(can_delete) # Explicitly cast to bool if it's an Optional[bool]
        return False

    @staticmethod
    async def can_bot_restrict_members(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        bot_member = await PermissionService.get_bot_permissions(chat_id, context)
        if bot_member and isinstance(bot_member, ChatMember.ADMINISTRATOR):
            can_restrict = bot_member.can_restrict_members
            logger.debug(f"Bot can_restrict_members in chat {chat_id}: {can_restrict}")
            return bool(can_restrict)
        return False
        
    @staticmethod
    async def bot_is_admin_with_essential_rights(chat_id: int, context: ContextTypes.DEFAULT_TYPE, notify_chat: bool = False) -> bool:
        """Checks if bot is admin and has rights to delete messages and restrict users."""
        bot_member = await PermissionService.get_bot_permissions(chat_id, context, force_refresh=True) # Force refresh for this important check
        
        if not bot_member or bot_member.status != ChatMemberStatus.ADMINISTRATOR:
            if notify_chat:
                await context.bot.send_message(chat_id, "برای عملکرد صحیح، ربات باید مدیر گروه باشد.")
            return False

        # Ensure bot_member is ChatMember.Administrator to access specific rights
        if isinstance(bot_member, ChatMember.ADMINISTRATOR):
            can_delete = bot_member.can_delete_messages
            can_restrict = bot_member.can_restrict_members
            
            if can_delete and can_restrict:
                logger.info(f"Bot has essential admin rights (delete, restrict) in chat {chat_id}.")
                return True
            else:
                missing_rights = []
                if not can_delete: missing_rights.append("حذف پیام‌ها")
                if not can_restrict: missing_rights.append("محدود کردن کاربران")
                
                if notify_chat:
                    await context.bot.send_message(
                        chat_id,
                        f"ربات مدیر است اما مجوزهای لازم را ندارد. لطفاً مجوزهای زیر را اعطا کنید: {', '.join(missing_rights)}"
                    )
                logger.warning(f"Bot is admin in chat {chat_id} but lacks essential rights: {', '.join(missing_rights)}")
                return False
        else: # Should not happen if status is ADMINISTRATOR, but as a safeguard
            logger.error(f"Bot status is ADMINISTRATOR but object type is {type(bot_member)} in chat {chat_id}")
            if notify_chat:
                 await context.bot.send_message(chat_id, "خطای داخلی در بررسی مجوزهای ربات. لطفاً با توسعه‌دهنده تماس بگیرید.")
            return False

    @staticmethod
    def clear_permission_cache(chat_id: int):
        if chat_id in _bot_permissions_cache:
            del _bot_permissions_cache[chat_id]
            logger.info(f"Cleared bot permission cache for chat {chat_id}.")


# Decorator using the new class-based structure
# Retains the same logic but calls the class method.
# The decorator itself remains a module-level function.
def require_admin_privileges(handler_func):
    """Decorator to restrict access to admin users only."""
    # Ensure the wrapper is async if handler_func is async
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            logger.warning("Admin command received without an effective user.")
            # Consider replying if possible, or just returning
            # await update.message.reply_text("Could not identify user for permission check.")
            return

        # Call the refactored is_user_admin_or_owner (which is now a module-level async function)
        is_admin = await is_user_admin_or_owner(update, context) # No need to pass user_id if checking effective_user
        
        if is_admin:
            return await handler_func(update, context, *args, **kwargs)
        else:
            user_info = f"User {update.effective_user.id} ({update.effective_user.name})"
            chat_info = f"chat {update.effective_chat.id if update.effective_chat else 'N/A'}"
            logger.warning(f"{user_info} tried to use an admin command without privileges in {chat_info}.")
            
            # Use BotMessages for consistency if defined, otherwise fallback
            # from telegram_bot.core.constants import BotMessages # Import if not already at top level
            # permission_denied_message = getattr(BotMessages, "PERMISSION_DENIED", "You don't have permission to use this command.")

            if update.message:
                await update.message.reply_text("شما مجوز استفاده از این دستور را ندارید.")
            elif update.callback_query:
                await update.callback_query.answer("شما مجوز این عملیات را ندارید.", show_alert=True)
            return
    return wrapper

# Note: The __main__ block is removed as direct execution of this service module is not typical.
# Testing would be done via integration tests or by running the main bot.

# is_bot_admin function is now PermissionService.bot_is_admin
# get_user_status_in_chat remains a module-level helper for now, or could be part of PermissionService too.

