class BotConstants:
    FLOOD_MAX_MESSAGES: int = 5
    FLOOD_TIME_WINDOW_SECONDS: int = 10
    FLOOD_MUTE_DURATION_MINUTES: int = 1
    DEFAULT_WELCOME_MESSAGE: str = "👋 سلام {user_mention} عزیز، به گروه {chat_title} خوش آمدید!"
    DEFAULT_RULES_TEXT: str = "هنوز قانونی برای این گروه تنظیم نشده است."
    MAX_RULES_LENGTH: int = 4000
    MAX_WELCOME_MESSAGE_LENGTH: int = 1000
