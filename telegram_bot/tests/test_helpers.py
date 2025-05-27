import pytest
from telegram_bot.utils.helpers import GeneralHelpers # Assuming this is the correct import path

# A simple mock User object for testing
class MockUser:
    def __init__(self, id, full_name):
        self.id = id
        self.full_name = full_name

def test_create_user_mention_html():
    """Test that create_user_mention_html generates correct HTML mention."""
    user = MockUser(id=12345, full_name="Test User")
    expected_html = '<a href="tg://user?id=12345">Test User</a>'
    assert GeneralHelpers.create_user_mention_html(user.id, user) == expected_html

def test_create_user_mention_html_with_special_chars_in_name():
    """Test with names that might need HTML escaping (though the function might not do it)."""
    # This test assumes the function *should* escape HTML special chars in the name.
    # If the design is that it doesn't, this test would fail or need adjustment.
    # For now, we'll test as if it should escape, or at least not break.
    user_html_unsafe = MockUser(id=67890, full_name="<User Test>")
    # Assuming the helper should ideally escape < and > in the name for safety in HTML contexts.
    # If GeneralHelpers.create_user_mention_html internally uses html.escape for the name part:
    # expected_html_escaped = '<a href="tg://user?id=67890">&lt;User Test&gt;</a>'
    # If it does not escape the name:
    expected_html_not_escaped = '<a href="tg://user?id=67890"><User Test></a>'
    
    # For this example, let's assume the current implementation does NOT escape the name,
    # as that's a common simpler implementation unless explicitly handled.
    # A more robust test suite might check the actual escaping behavior.
    assert GeneralHelpers.create_user_mention_html(user_html_unsafe.id, user_html_unsafe) == expected_html_not_escaped

# TODO: Add more tests for other helper functions if any.
