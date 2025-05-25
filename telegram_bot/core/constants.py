class BotConstants:
    FLOOD_MAX_MESSAGES: int = 5
    FLOOD_TIME_WINDOW_SECONDS: int = 10
    FLOOD_MUTE_DURATION_MINUTES: int = 1
    DEFAULT_WELCOME_MESSAGE: str = "👋 سلام {user_mention} عزیز، به گروه {chat_title} خوش آمدید!"
    DEFAULT_RULES_TEXT: str = "هنوز قانونی برای این گروه تنظیم نشده است."
    MAX_RULES_LENGTH: int = 4000
    MAX_WELCOME_MESSAGE_LENGTH: int = 1000


class BotMessages:
    DB_ERROR_MESSAGE: str = "خطایی در ارتباط با پایگاه داده رخ داد. لطفاً بعداً تلاش کنید."
    GENERIC_ERROR_MESSAGE: str = "یک خطای پیش‌بینی نشده رخ داد. لطفاً دوباره تلاش کنید."
    WELCOME_MESSAGE_PROMPT: str = (
        "لطفاً متن پیام خوشامدگویی جدید را ارسال کنید.\n"
        "می‌توانید از متغیرهای زیر استفاده کنید:\n"
        "- `{user_mention}`: منشن کاربر (مثلاً @username یا نام کامل لینک شده)\n"
        "- `{user_name}`: نام کامل کاربر\n"
        "- `{chat_title}`: عنوان گروه"
    )
    FAREWELL_MESSAGE_PROMPT: str = (
        "لطفاً متن پیام بدرقه جدید را ارسال کنید.\n"
        "می‌توانید از متغیرهای زیر استفاده کنید:\n"
        "- `{user_mention}`: منشن کاربر\n"
        "- `{user_name}`: نام کامل کاربر\n"
        "- `{chat_title}`: عنوان گروه"
    )
    RULES_PROMPT: str = "لطفاً متن قوانین جدید گروه را ارسال کنید."
    MAX_MESSAGES_PROMPT: str = "لطفاً حداکثر تعداد پیام مجاز در بازه زمانی ضد سیلاب (مثلاً برای ۱۰ ثانیه) را به صورت عددی وارد کنید."
    PERMISSION_DENIED: str = "شما مجوز لازم برای انجام این کار را ندارید."
    BOT_NOT_ADMIN_ENOUGH: str = (
        "متاسفانه من مجوزهای لازم برای انجام این کار را در گروه ندارم. "
        "لطفاً بررسی کنید که من مدیر گروه هستم و مجوزهای 'حذف پیام‌ها' و 'محدود کردن کاربران' را دارم."
    )
