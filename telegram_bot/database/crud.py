"""
عملیات CRUD (Create, Read, Update, Delete) برای مدل‌های پایگاه داده.

این ماژول کلاس‌هایی را ارائه می‌دهد که هر کدام شامل مجموعه‌ای از متدهای استاتیک
برای تعامل با جداول مربوطه در پایگاه داده (مانند group_settings, forbidden_words,
user_flood_records) به صورت آسنکرون هستند.
"""
import logging
from datetime import datetime, timedelta # Added
from sqlalchemy import delete # Added
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select 
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, TypeVar, Type
from telegram_bot.database import models 
from telegram_bot.database.models import GroupSetting, ForbiddenWord, UserFloodRecord 

logger = logging.getLogger(__name__)

class GroupSettingCRUD:
    """ارائه متدهای CRUD برای مدیریت تنظیمات گروه (GroupSetting)."""
    @staticmethod
    async def get_or_create(session: AsyncSession, group_id: int, chat_title: Optional[str] = None) -> Optional[models.GroupSetting]:
        """
        تنظیمات یک گروه را بازیابی می‌کند یا در صورت عدم وجود، ایجاد می‌کند.

        اگر تنظیمات برای گروه وجود نداشته باشد، یک رکورد جدید با مقادیر پیش‌فرض
        و عنوان گروه (در صورت ارائه) ایجاد می‌شود. اگر عنوان گروه تغییر کرده باشد،
        عنوان موجود در پایگاه داده به‌روزرسانی می‌شود.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            chat_title: عنوان فعلی گروه تلگرامی (اختیاری).

        Returns:
            شیء GroupSetting در صورت موفقیت، در غیر این صورت None.
        """
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
        """
        فیلدهای مشخصی از تنظیمات یک گروه را به‌روزرسانی می‌کند.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            **kwargs: جفت‌های کلید-مقدار برای فیلدهایی که باید به‌روزرسانی شوند.

        Returns:
            شیء GroupSetting به‌روزرسانی شده در صورت موفقیت، در غیر این صورت None.
        """
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
    """ارائه متدهای CRUD برای مدیریت کلمات ممنوعه (ForbiddenWord)."""
    @staticmethod
    async def create(session: AsyncSession, group_id: int, word: str) -> Optional[models.ForbiddenWord]:
        """
        یک کلمه ممنوعه جدید به گروه اضافه می‌کند.

        کلمه ابتدا به حروف کوچک تبدیل شده و فاصله‌های اضافی آن حذف می‌شود.
        اگر کلمه از قبل در لیست کلمات ممنوعه گروه وجود داشته باشد، رکورد موجود بازگردانده می‌شود.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            word: کلمه‌ای که باید به لیست ممنوعه اضافه شود.

        Returns:
            شیء ForbiddenWord ایجاد یا بازیابی شده در صورت موفقیت، در غیر این صورت None.
        """
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
        """
        یک کلمه ممنوعه را از لیست کلمات ممنوعه گروه حذف می‌کند.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            word: کلمه‌ای که باید از لیست ممنوعه حذف شود.

        Returns:
            True اگر کلمه با موفقیت حذف شد، False در غیر این صورت (مثلاً اگر کلمه یافت نشد).
        """
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
        """
        لیست تمامی کلمات ممنوعه برای یک گروه خاص را بازیابی می‌کند.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.

        Returns:
            لیستی از رشته‌ها که هر کدام یک کلمه ممنوعه است. در صورت خطا یا عدم وجود، لیست خالی بازمی‌گرداند.
        """
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
    """ارائه متدهای CRUD برای مدیریت سوابق کاربران برای کنترل سیلاب (UserFloodRecord)."""
    @staticmethod
    async def get_or_create(session: AsyncSession, group_id: int, user_id: int) -> Optional[models.UserFloodRecord]:
        """
        سابقه کنترل سیلاب یک کاربر در یک گروه را بازیابی می‌کند یا در صورت عدم وجود، ایجاد می‌کند.

        اگر سابقه برای ترکیب کاربر و گروه وجود نداشته باشد، یک رکورد جدید با تعداد تخلف صفر ایجاد می‌شود.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            user_id: شناسه کاربر تلگرامی.

        Returns:
            شیء UserFloodRecord در صورت موفقیت، در غیر این صورت None.
        """
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
    async def update(session: AsyncSession, group_id: int, user_id: int, update_last_infraction_timestamp: bool = False, increment_infraction: bool = False) -> Optional[models.UserFloodRecord]:
        """
        سابقه کنترل سیلاب یک کاربر را به‌روزرسانی می‌کند.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            user_id: شناسه کاربر تلگرامی.
            update_last_infraction_timestamp: اگر True باشد، زمان آخرین تخلف به زمان فعلی به‌روز می‌شود.
            increment_infraction: اگر True باشد، تعداد تخلفات یک واحد افزایش می‌یابد.

        Returns:
            شیء UserFloodRecord به‌روزرسانی شده در صورت موفقیت، در غیر این صورت None.
        """
        try:
            record = await UserFloodRecordCRUD.get_or_create(session, group_id, user_id) # Use the class method
            if not record:
                return None

            if update_last_infraction_timestamp:
                from sqlalchemy.sql import func
                record.last_infraction_timestamp = func.now()
                logger.debug(f"Updated last infraction timestamp for user {user_id} in group {group_id} (UserFloodRecordCRUD.update).")

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
        """
        تعداد تخلفات یک کاربر در یک گروه را صفر می‌کند.

        Args:
            session: نشست پایگاه داده آسنکرون.
            group_id: شناسه گروه تلگرامی.
            user_id: شناسه کاربر تلگرامی.

        Returns:
            شیء UserFloodRecord با تعداد تخلفات صفر شده در صورت موفقیت، در غیر این صورت None.
        """
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

    @staticmethod
    async def clear_old_records(session: AsyncSession, older_than_seconds: int) -> Optional[int]:
        """
        Deletes flood records older than a specified time threshold.

        Args:
            session: The asynchronous database session.
            older_than_seconds: The threshold in seconds. Records with a 
                                `last_infraction_timestamp` older than this will be deleted.

        Returns:
            The number of records deleted, or None if an error occurred.
        """
        try:
            threshold_datetime = datetime.utcnow() - timedelta(seconds=older_than_seconds)
            
            stmt = delete(models.UserFloodRecord).where(
                models.UserFloodRecord.last_infraction_timestamp < threshold_datetime
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Successfully deleted {deleted_count} old flood records (older than {older_than_seconds} seconds).")
            return deleted_count
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error while clearing old flood records: {e}", exc_info=True)
            return None
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error while clearing old flood records: {e}", exc_info=True)
            return None
