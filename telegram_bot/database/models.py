"""
تعریف مدل‌های داده SQLAlchemy برای پایگاه داده ربات.

این ماژول شامل کلاس‌هایی است که هر کدام نمایانگر یک جدول در پایگاه داده هستند
و ستون‌ها، روابط و محدودیت‌های آن‌ها را تعریف می‌کنند.
مدل‌ها شامل GroupSetting (تنظیمات گروه)، ForbiddenWord (کلمات ممنوعه)
و UserFloodRecord (سوابق کاربران برای کنترل سیلاب) می‌باشند.
"""
import logging
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)
Base = declarative_base()

class GroupSetting(Base):
    """
    نگهداری تنظیمات مربوط به هر گروه تلگرامی که ربات در آن فعال است.
    شامل تنظیمات مربوط به پیام خوشامدگویی/بدرقه، فیلترهای محتوا،
    سیستم ضد سیلاب و سایر پیکربندی‌های خاص گروه.
    """
    __tablename__ = "group_settings"

    id = Column(Integer, primary_key=True, index=True) # شناسه یکتای رکورد تنظیمات
    group_id = Column(BigInteger, unique=True, index=True, nullable=False) # شناسه یکتای گروه تلگرامی
    chat_title = Column(String, nullable=True) # عنوان گروه تلگرامی، برای نمایش بهتر
    is_bot_active = Column(Boolean, default=True) # وضعیت کلی فعال بودن ربات در گروه
    welcome_message = Column(String, default="Welcome to the group, {user_mention}!") # پیام خوشامدگویی. متغیرها: {user_mention}, {chat_title}, {user_name}
    welcome_message_active = Column(Boolean, default=False) # آیا پیام خوشامدگویی فعال است؟
    farewell_message = Column(String, default="Goodbye, {user_name}!") # پیام بدرقه. متغیرها: {user_mention}, {chat_title}, {user_name}
    farewell_message_active = Column(Boolean, default=False) # آیا پیام بدرقه فعال است؟
    filter_links_active = Column(Boolean, default=False) # آیا فیلتر لینک‌ها فعال است؟
    filter_forwards_active = Column(Boolean, default=False) # آیا فیلتر پیام‌های فروارد شده فعال است؟
    filter_forbidden_words_active = Column(Boolean, default=False) # آیا فیلتر کلمات ممنوعه فعال است؟
    anti_flood_active = Column(Boolean, default=True) # آیا سیستم ضد سیلاب (anti-flood) فعال است؟
    max_messages_per_minute = Column(Integer, default=10) # حداکثر تعداد پیام مجاز در دقیقه برای سیستم ضد سیلاب
    warn_on_infraction = Column(Boolean, default=True) # آیا پس از اولین تخلف ضد سیلاب هشدار داده شود؟
    kick_on_infraction = Column(Boolean, default=False) # آیا پس از N تخلف، کاربر اخراج شود؟
    ban_on_infraction = Column(Boolean, default=False) # آیا پس از N تخلف، کاربر مسدود (ban) شود؟
    infraction_count_for_action = Column(Integer, default=3) # تعداد تخلفات لازم برای اجرای عمل (اخراج/مسدود کردن)

    forbidden_words = relationship("ForbiddenWord", back_populates="group_setting", cascade="all, delete-orphan") # لیست کلمات ممنوعه مرتبط با این گروه

    def __repr__(self):
        return f"<GroupSetting(group_id={self.group_id}, is_bot_active={self.is_bot_active})>"

class ForbiddenWord(Base):
    """
    نگهداری کلمات یا عبارات ممنوعه برای هر گروه.
    هر رکورد به یک GroupSetting مرتبط است.
    """
    __tablename__ = "forbidden_words"

    id = Column(Integer, primary_key=True, index=True) # شناسه یکتای کلمه ممنوعه
    group_setting_id = Column(Integer, ForeignKey("group_settings.id"), nullable=False) # کلید خارجی به جدول group_settings
    word = Column(String, nullable=False) # کلمه یا عبارت ممنوعه

    group_setting = relationship("GroupSetting", back_populates="forbidden_words") # ارتباط با تنظیمات گروه

    __table_args__ = (UniqueConstraint('group_setting_id', 'word', name='_group_word_uc'),) # اطمینان از عدم تکرار کلمه در یک گروه

    def __repr__(self):
        return f"<ForbiddenWord(word='{self.word}', group_id={self.group_setting.group_id if self.group_setting else 'N/A'})>"


class UserFloodRecord(Base):
    """
    ذخیره اطلاعات مربوط به فعالیت کاربران در گروه‌ها برای سیستم ضد سیلاب.
    شامل تعداد تخلفات کاربر و زمان آخرین تخلف ثبت شده برای ترکیب کاربر و گروه.
    """
    __tablename__ = "user_flood_records"

    id = Column(Integer, primary_key=True, index=True) # شناسه یکتای رکورد سیلاب
    user_id = Column(BigInteger, index=True, nullable=False) # شناسه کاربر تلگرامی
    group_id = Column(BigInteger, index=True, nullable=False) # شناسه گروه تلگرامی
    last_infraction_timestamp = Column(DateTime, default=func.now()) # زمان آخرین تخلف ثبت شده برای این کاربر در این گروه
    infraction_count = Column(Integer, default=0) # تعداد کل تخلفات ثبت شده

    __table_args__ = (UniqueConstraint('user_id', 'group_id', name='_user_group_uc'),) # اطمینان از یکتایی رکورد برای هر کاربر در هر گروه


    def __repr__(self):
        return f"<UserFloodRecord(user_id={self.user_id}, group_id={self.group_id}, infractions={self.infraction_count})>"

# Example of how to run this (for testing or setup)
if __name__ == "__main__":
    from sqlalchemy import create_engine
    from telegram_bot.config import settings # Assuming your settings are accessible

    logger.info("Creating database tables from models.py...")
    # In a real app, use Alembic for migrations.
    # This is a simplified setup for demonstration or initial creation.
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    logger.info("Database tables created (if they didn't exist).")
