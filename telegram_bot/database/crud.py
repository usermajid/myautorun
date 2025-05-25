import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select # For SQLAlchemy 2.0 style select
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, TypeVar, Type
from telegram_bot.database import models # Assuming models.py defines GroupSetting, ForbiddenWord, UserFloodRecord
from telegram_bot.database.models import GroupSetting, ForbiddenWord, UserFloodRecord # Explicit imports

logger = logging.getLogger(__name__)

class GroupSettingCRUD:
    @staticmethod
    async def get_or_create(session: AsyncSession, group_id: int, chat_title: Optional[str] = None) -> Optional[models.GroupSetting]:
        """Fetches a group setting or creates it if it doesn't exist (async)."""
        try:
            stmt = select(models.GroupSetting).where(models.GroupSetting.group_id == group_id)
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()

            if not setting:
                logger.info(f"No settings found for group {group_id}, creating new entry.")
                setting = models.GroupSetting(group_id=group_id, chat_title=chat_title)
                session.add(setting)
                await session.commit()
                await session.refresh(setting)
                logger.info(f"Successfully created settings for group {group_id}.")
            elif chat_title and setting.chat_title != chat_title:
                setting.chat_title = chat_title
                await session.commit()
                await session.refresh(setting)
                logger.info(f"Updated chat_title for group {group_id} to {chat_title}.")
            return setting
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in GroupSettingCRUD.get_or_create for group {group_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in GroupSettingCRUD.get_or_create for group {group_id}: {e}", exc_info=True)
            return None

    @staticmethod
    async def update(session: AsyncSession, group_id: int, **kwargs) -> Optional[models.GroupSetting]:
        """Updates specific fields of a group setting (async)."""
        try:
            stmt = select(models.GroupSetting).where(models.GroupSetting.group_id == group_id)
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting:
                for key, value in kwargs.items():
                    if hasattr(setting, key):
                        setattr(setting, key, value)
                    else:
                        logger.warning(f"Attempted to update non-existent attribute '{key}' for group {group_id} in GroupSettingCRUD.update.")
                await session.commit()
                await session.refresh(setting)
                logger.info(f"Successfully updated settings for group {group_id} with {kwargs} in GroupSettingCRUD.update.")
            else:
                logger.warning(f"Settings not found for group {group_id} during update attempt in GroupSettingCRUD.update.")
            return setting
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error in GroupSettingCRUD.update for group {group_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in GroupSettingCRUD.update for group {group_id}: {e}", exc_info=True)
            return None

class ForbiddenWordCRUD:
    @staticmethod
    async def create(session: AsyncSession, group_id: int, word: str) -> Optional[models.ForbiddenWord]:
        """Adds a forbidden word for a specific group (async). Renamed from add_forbidden_word."""
        try:
            group_setting = await GroupSettingCRUD.get_or_create(session, group_id) # Use the class method
            if not group_setting or not group_setting.id:
                logger.error(f"Could not add forbidden word. Group setting not found or ID missing for group {group_id} in ForbiddenWordCRUD.create.")
                return None

            word_lower = word.strip().lower()
            if not word_lower:
                logger.warning(f"Attempt to add empty forbidden word for group {group_id} in ForbiddenWordCRUD.create.")
                return None

            stmt = select(models.ForbiddenWord).where(
                models.ForbiddenWord.group_setting_id == group_setting.id,
                models.ForbiddenWord.word == word_lower
            )
            result = await session.execute(stmt)
            existing_word = result.scalar_one_or_none()

            if existing_word:
                logger.info(f"Word '{word_lower}' already forbidden in group {group_id} (ForbiddenWordCRUD.create).")
                return existing_word

            forbidden_word = models.ForbiddenWord(group_setting_id=group_setting.id, word=word_lower)
            session.add(forbidden_word)
            await session.commit()
            await session.refresh(forbidden_word)
            logger.info(f"Added forbidden word '{word_lower}' to group {group_id} (ForbiddenWordCRUD.create).")
            return forbidden_word
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error adding forbidden word '{word}' to group {group_id} in ForbiddenWordCRUD.create: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error adding forbidden word '{word}' to group {group_id} in ForbiddenWordCRUD.create: {e}", exc_info=True)
            return None

    @staticmethod
    async def delete(session: AsyncSession, group_id: int, word: str) -> bool:
        """Removes a forbidden word for a specific group (async). Renamed from remove_forbidden_word."""
        try:
            group_setting = await GroupSettingCRUD.get_or_create(session, group_id) # Use the class method
            if not group_setting or not group_setting.id:
                logger.error(f"Could not remove forbidden word. Group setting not found or ID missing for group {group_id} in ForbiddenWordCRUD.delete.")
                return False

            word_lower = word.strip().lower()
            stmt = select(models.ForbiddenWord).where(
                models.ForbiddenWord.group_setting_id == group_setting.id,
                models.ForbiddenWord.word == word_lower
            )
            result = await session.execute(stmt)
            forbidden_word_obj = result.scalar_one_or_none()

            if forbidden_word_obj:
                await session.delete(forbidden_word_obj)
                await session.commit()
                logger.info(f"Removed forbidden word '{word_lower}' from group {group_id} (ForbiddenWordCRUD.delete).")
                return True
            logger.info(f"Forbidden word '{word_lower}' not found in group {group_id} for removal (ForbiddenWordCRUD.delete).")
            return False
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error removing forbidden word '{word}' from group {group_id} in ForbiddenWordCRUD.delete: {e}", exc_info=True)
            return False
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error removing forbidden word '{word}' from group {group_id} in ForbiddenWordCRUD.delete: {e}", exc_info=True)
            return False

    @staticmethod
    async def get_all_words_for_group(session: AsyncSession, group_id: int) -> List[str]:
        """Retrieves all forbidden words for a specific group (async). Renamed from get_forbidden_words."""
        try:
            group_setting = await GroupSettingCRUD.get_or_create(session, group_id) # Use the class method
            if not group_setting or not group_setting.id:
                logger.error(f"Could not retrieve forbidden words. Group setting not found or ID missing for group {group_id} in ForbiddenWordCRUD.get_all_words_for_group.")
                return []

            stmt = select(models.ForbiddenWord.word).where(models.ForbiddenWord.group_setting_id == group_setting.id)
            result = await session.execute(stmt)
            words = [row[0] for row in result.fetchall()]
            logger.debug(f"Retrieved {len(words)} forbidden words for group {group_id} (ForbiddenWordCRUD.get_all_words_for_group).")
            return words
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving forbidden words for group {group_id} in ForbiddenWordCRUD.get_all_words_for_group: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving forbidden words for group {group_id} in ForbiddenWordCRUD.get_all_words_for_group: {e}", exc_info=True)
            return []

class UserFloodRecordCRUD:
    @staticmethod
    async def get_or_create(session: AsyncSession, group_id: int, user_id: int) -> Optional[models.UserFloodRecord]:
        """Fetches or creates a flood record for a user in a group (async)."""
        try:
            stmt = select(models.UserFloodRecord).where(
                models.UserFloodRecord.group_id == group_id,
                models.UserFloodRecord.user_id == user_id
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if not record:
                logger.info(f"Creating new flood record for user {user_id} in group {group_id} (UserFloodRecordCRUD.get_or_create).")
                record = models.UserFloodRecord(group_id=group_id, user_id=user_id, infraction_count=0)
                session.add(record)
                await session.commit()
                await session.refresh(record)
            return record
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"DB error in UserFloodRecordCRUD.get_or_create for user {user_id}, group {group_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in UserFloodRecordCRUD.get_or_create for user {user_id}, group {group_id}: {e}", exc_info=True)
            return None

    @staticmethod
    async def update(session: AsyncSession, group_id: int, user_id: int, update_timestamp: bool = False, increment_infraction: bool = False) -> Optional[models.UserFloodRecord]:
        """
        Updates a user's flood record (async).
        - `update_timestamp`: If True, updates `message_timestamps` to current time.
        - `increment_infraction`: If True, increments `infraction_count`.
        """
        try:
            record = await UserFloodRecordCRUD.get_or_create(session, group_id, user_id) # Use the class method
            if not record:
                return None

            if update_timestamp:
                from sqlalchemy.sql import func
                record.message_timestamps = func.now()
                logger.debug(f"Updated message timestamp for user {user_id} in group {group_id} (UserFloodRecordCRUD.update).")

            if increment_infraction:
                record.infraction_count = (record.infraction_count or 0) + 1
                logger.info(f"Incremented infraction count for user {user_id} in group {group_id} to {record.infraction_count} (UserFloodRecordCRUD.update).")

            await session.commit()
            await session.refresh(record)
            return record
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"DB error updating flood record for user {user_id}, group {group_id} in UserFloodRecordCRUD.update: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error updating flood record for user {user_id}, group {group_id} in UserFloodRecordCRUD.update: {e}", exc_info=True)
            return None

    @staticmethod
    async def reset_infractions(session: AsyncSession, group_id: int, user_id: int) -> Optional[models.UserFloodRecord]:
        """Resets a user's infraction count in a group (async). Renamed from reset_user_infraction_count."""
        try:
            record = await UserFloodRecordCRUD.get_or_create(session, group_id, user_id) # Use the class method
            if record:
                record.infraction_count = 0
                await session.commit()
                await session.refresh(record)
                logger.info(f"Reset infraction count for user {user_id} in group {group_id} (UserFloodRecordCRUD.reset_infractions).")
            return record
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"DB error resetting infractions for user {user_id}, group {group_id} in UserFloodRecordCRUD.reset_infractions: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error resetting infractions for user {user_id}, group {group_id} in UserFloodRecordCRUD.reset_infractions: {e}", exc_info=True)
            return None
