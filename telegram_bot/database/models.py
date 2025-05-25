import logging
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)
Base = declarative_base()

class GroupSetting(Base):
    __tablename__ = "group_settings"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(BigInteger, unique=True, index=True, nullable=False)
    chat_title = Column(String, nullable=True) # Added chat_title
    is_bot_active = Column(Boolean, default=True)
    welcome_message = Column(String, default="Welcome to the group, {user_mention}!")
    welcome_message_active = Column(Boolean, default=False) # New
    farewell_message = Column(String, default="Goodbye, {user_name}!")
    farewell_message_active = Column(Boolean, default=False) # New
    filter_links_active = Column(Boolean, default=False) # Renamed from allow_links, default inverted
    filter_forwards_active = Column(Boolean, default=False) # Renamed from allow_forwards, default inverted
    anti_flood_active = Column(Boolean, default=True) # Renamed from flood_control_enabled
    max_messages_per_minute = Column(Integer, default=10) # Example value
    warn_on_infraction = Column(Boolean, default=True)
    kick_on_infraction = Column(Boolean, default=False) # Kicks after N infractions
    ban_on_infraction = Column(Boolean, default=False) # Bans after N infractions
    infraction_count_for_action = Column(Integer, default=3) # N infractions

    forbidden_words = relationship("ForbiddenWord", back_populates="group_setting", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GroupSetting(group_id={self.group_id}, is_bot_active={self.is_bot_active})>"

class ForbiddenWord(Base):
    __tablename__ = "forbidden_words"

    id = Column(Integer, primary_key=True, index=True)
    group_setting_id = Column(Integer, ForeignKey("group_settings.id"), nullable=False)
    word = Column(String, nullable=False)

    group_setting = relationship("GroupSetting", back_populates="forbidden_words")

    __table_args__ = (UniqueConstraint('group_setting_id', 'word', name='_group_word_uc'),)

    def __repr__(self):
        return f"<ForbiddenWord(word='{self.word}', group_id={self.group_setting.group_id if self.group_setting else 'N/A'})>"


class UserFloodRecord(Base):
    __tablename__ = "user_flood_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    group_id = Column(BigInteger, index=True, nullable=False) # Added group_id
    message_timestamps = Column(DateTime, default=func.now()) # Store timestamp of each message
    infraction_count = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint('user_id', 'group_id', name='_user_group_uc'),)


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
