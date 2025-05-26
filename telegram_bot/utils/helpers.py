import logging
from telegram import Update, User # Ensure User is imported
from typing import Optional # Ensure Optional is imported
import html # Add this import

logger = logging.getLogger(__name__)

# Removed get_user_mention function
# Removed is_user_admin function

def get_group_id(update: Update) -> Optional[int]:
    """Extracts group ID from an update more reliably."""
    if update.effective_chat:
        return update.effective_chat.id
    logger.warning("Could not extract group_id from update.")
    return None

class GeneralHelpers:
    @staticmethod
    def create_user_mention_html(user_id: int, user_obj: Optional[User] = None) -> str:
        """Creates an HTML mention link for a user."""
        # Ensure user_id is an int, as it might come from various sources
        user_id = int(user_id)
        
        if user_obj and user_obj.username:
            # Telegram automatically links @usernames in HTML parse mode
            return f"@{html.escape(user_obj.username)}"
        elif user_obj and user_obj.full_name:
            # Escape full_name to prevent HTML injection if name contains HTML characters
            return f"<a href='tg://user?id={user_id}'>{html.escape(user_obj.full_name)}</a>"
        elif user_obj: # User object exists but no username and no full_name (rare)
            return f"<a href='tg://user?id={user_id}'>User {user_id}</a>"
        else: # No user object, just an ID
            return f"User ID <code>{user_id}</code>" # Using <code> for ID-only makes it distinct

    @staticmethod
    def format_welcome_message(template: str, user_mention: str, chat_title: str) -> str:
        """
        Formats a welcome or farewell message template with provided placeholders.
        Placeholders: {user_mention}, {user_name} (from user_mention if it's full name), {chat_title}
        """
        # Basic placeholder for user_name if user_mention is already a full name link
        # A more robust solution might require passing user_name separately if user_mention is just @username
        user_name_placeholder = user_mention # Default to mention if specific name not easily extracted
        
        # Attempt to extract name if user_mention is an HTML link (very basic parsing)
        if user_mention.startswith("<a href="):
            try:
                # Extracts text between > and </a>
                name_match = html.unescape(user_mention.split('>')[1].split('<')[0])
                if name_match:
                    user_name_placeholder = name_match
            except IndexError:
                pass # Keep default if parsing fails

        return template.format(
            user_mention=user_mention,
            user_name=user_name_placeholder, # Use the extracted or default name
            chat_title=chat_title
        )


if __name__ == "__main__":
    logger.info("Helpers module loaded. Contains utility functions in GeneralHelpers class.")
    # Example (conceptual, as User object needs to be created appropriately):
    # test_user_with_username = User(id=1, first_name="Test", is_bot=False, username="testuser")
    # test_user_without_username = User(id=2, first_name="Test NoUser", is_bot=False, last_name="Example")
    # test_user_id_only = 3

    # print(f"Mention for user with username: {GeneralHelpers.create_user_mention_html(test_user_with_username.id, test_user_with_username)}")
    # print(f"Mention for user without username: {GeneralHelpers.create_user_mention_html(test_user_without_username.id, test_user_without_username)}")
    # print(f"Mention for user ID only: {GeneralHelpers.create_user_mention_html(test_user_id_only)}")

    # template = "Hello {user_mention} ({user_name}), welcome to {chat_title}!"
    # mention = GeneralHelpers.create_user_mention_html(test_user_without_username.id, test_user_without_username)
    # print(GeneralHelpers.format_welcome_message(template, mention, "Awesome Group"))
    pass
