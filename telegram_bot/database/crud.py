import logging
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from telegram_bot.database import models
from telegram_bot.database.models import GroupSetting, ForbiddenWord, UserFloodRecord # Ensure direct import for clarity

logger = logging.getLogger(__name__)

# General CRUD operations
def get_or_create_group_setting(db: Session, group_id: int) -> Optional[models.GroupSetting]:
    """Fetches a group setting or creates it if it doesn't exist."""
    try:
        setting = db.query(models.GroupSetting).filter(models.GroupSetting.group_id == group_id).first()
        if not setting:
            logger.info(f"No settings found for group {group_id}, creating new entry.")
            setting = models.GroupSetting(group_id=group_id)
            db.add(setting)
            db.commit()
            db.refresh(setting)
            logger.info(f"Successfully created settings for group {group_id}.")
        return setting
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in get_or_create_group_setting for group {group_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in get_or_create_group_setting for group {group_id}: {e}", exc_info=True)
        return None

def update_group_setting(db: Session, group_id: int, **kwargs) -> Optional[models.GroupSetting]:
    """Updates specific fields of a group setting."""
    try:
        setting = get_or_create_group_setting(db, group_id)
        if setting:
            for key, value in kwargs.items():
                if hasattr(setting, key):
                    setattr(setting, key, value)
                else:
                    logger.warning(f"Attempted to update non-existent attribute '{key}' for group {group_id}.")
            db.commit()
            db.refresh(setting)
            logger.info(f"Successfully updated settings for group {group_id}.")
        return setting
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in update_group_setting for group {group_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in update_group_setting for group {group_id}: {e}", exc_info=True)
        return None


# Forbidden Words CRUD
def add_forbidden_word(db: Session, group_id: int, word: str) -> Optional[models.ForbiddenWord]:
    """Adds a forbidden word for a specific group."""
    try:
        group_setting = get_or_create_group_setting(db, group_id)
        if not group_setting:
            logger.error(f"Could not add forbidden word. Group setting not found for group {group_id}.")
            return None

        existing_word = db.query(models.ForbiddenWord).filter_by(group_setting_id=group_setting.id, word=word.lower()).first()
        if existing_word:
            logger.info(f"Word '{word}' already forbidden in group {group_id}.")
            return existing_word

        forbidden_word = models.ForbiddenWord(group_setting_id=group_setting.id, word=word.lower())
        db.add(forbidden_word)
        db.commit()
        db.refresh(forbidden_word)
        logger.info(f"Added forbidden word '{word}' to group {group_id}.")
        return forbidden_word
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error adding forbidden word '{word}' to group {group_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error adding forbidden word '{word}' to group {group_id}: {e}", exc_info=True)
        return None

def remove_forbidden_word(db: Session, group_id: int, word: str) -> bool:
    """Removes a forbidden word for a specific group."""
    try:
        group_setting = get_or_create_group_setting(db, group_id)
        if not group_setting:
            logger.error(f"Could not remove forbidden word. Group setting not found for group {group_id}.")
            return False

        forbidden_word_obj = db.query(models.ForbiddenWord).filter_by(group_setting_id=group_setting.id, word=word.lower()).first()
        if forbidden_word_obj:
            db.delete(forbidden_word_obj)
            db.commit()
            logger.info(f"Removed forbidden word '{word}' from group {group_id}.")
            return True
        logger.info(f"Forbidden word '{word}' not found in group {group_id} for removal.")
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error removing forbidden word '{word}' from group {group_id}: {e}", exc_info=True)
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error removing forbidden word '{word}' from group {group_id}: {e}", exc_info=True)
        return False

def get_forbidden_words(db: Session, group_id: int) -> List[str]:
    """Retrieves all forbidden words for a specific group."""
    try:
        group_setting = get_or_create_group_setting(db, group_id)
        if not group_setting:
            logger.error(f"Could not retrieve forbidden words. Group setting not found for group {group_id}.")
            return []
        # Ensure that the relationship loads the words correctly.
        # words = [fw.word for fw in group_setting.forbidden_words]
        # logger.debug(f"Retrieved {len(words)} forbidden words for group {group_id}.")
        # return words
        # Corrected way to query related objects if the above is not efficient or direct enough:
        words_query = db.query(models.ForbiddenWord.word).filter(models.ForbiddenWord.group_setting_id == group_setting.id).all()
        words = [word_tuple[0] for word_tuple in words_query]
        logger.debug(f"Retrieved {len(words)} forbidden words for group {group_id}: {words}")
        return words

    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving forbidden words for group {group_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error retrieving forbidden words for group {group_id}: {e}", exc_info=True)
        return []


# Flood Control CRUD
def get_or_create_user_flood_record(db: Session, group_id: int, user_id: int) -> Optional[UserFloodRecord]:
    """Fetches or creates a flood record for a user in a group."""
    try:
        record = db.query(UserFloodRecord).filter_by(group_id=group_id, user_id=user_id).first()
        if not record:
            record = UserFloodRecord(group_id=group_id, user_id=user_id, infraction_count=0)
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(f"Created new flood record for user {user_id} in group {group_id}.")
        return record
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB error in get_or_create_user_flood_record for user {user_id}, group {group_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in get_or_create_user_flood_record for user {user_id}, group {group_id}: {e}", exc_info=True)
        return None


def update_user_flood_record(db: Session, group_id: int, user_id: int, new_timestamp: Optional[bool] = False, increment_infraction: Optional[bool] = False) -> Optional[UserFloodRecord]:
    """
    Updates a user's flood record. Can add a new message timestamp or increment infraction count.
    Note: The original model stores a single `message_timestamps: DateTime`.
    This implies we are tracking the *last* message time or the *start* of a flood period,
    not a list of all messages. If a list is needed, the model needs to change.
    For simplicity, let's assume `message_timestamps` is updated to the latest message time
    when `new_timestamp` is True.
    """
    try:
        record = get_or_create_user_flood_record(db, group_id, user_id)
        if not record:
            return None # Error already logged by get_or_create

        if new_timestamp:
            from sqlalchemy.sql import func
            record.message_timestamps = func.now() # Update to current time
            logger.debug(f"Updated message timestamp for user {user_id} in group {group_id}.")

        if increment_infraction:
            record.infraction_count = (record.infraction_count or 0) + 1
            logger.info(f"Incremented infraction count for user {user_id} in group {group_id} to {record.infraction_count}.")

        db.commit()
        db.refresh(record)
        return record
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB error updating flood record for user {user_id}, group {group_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating flood record for user {user_id}, group {group_id}: {e}", exc_info=True)
        return None


def reset_user_infraction_count(db: Session, group_id: int, user_id: int) -> Optional[UserFloodRecord]:
    """Resets a user's infraction count in a group."""
    try:
        record = get_or_create_user_flood_record(db, group_id, user_id)
        if record:
            record.infraction_count = 0
            db.commit()
            db.refresh(record)
            logger.info(f"Reset infraction count for user {user_id} in group {group_id}.")
        return record
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB error resetting infractions for user {user_id}, group {group_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error resetting infractions for user {user_id}, group {group_id}: {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # This is for basic testing or direct script execution setup.
    # In a real application, you'd typically call these functions from your bot handlers.
    from telegram_bot.database.engine import SessionLocal, init_db
    from telegram_bot.core.logging_config import setup_logging
    setup_logging() # Configure logging

    logger.info("Running CRUD operations test script...")
    init_db() # Ensure tables are created

    db_session = SessionLocal()

    # Example: Test GroupSetting
    test_group_id = 12345
    settings = get_or_create_group_setting(db_session, test_group_id)
    if settings:
        logger.info(f"Settings for group {test_group_id}: {settings}")
        update_group_setting(db_session, test_group_id, welcome_message="Hello there!", allow_links=False)
        updated_settings = get_or_create_group_setting(db_session, test_group_id)
        logger.info(f"Updated settings for group {test_group_id}: {updated_settings}")

    # Example: Test ForbiddenWord
    add_forbidden_word(db_session, test_group_id, "spam")
    add_forbidden_word(db_session, test_group_id, "phish")
    words = get_forbidden_words(db_session, test_group_id)
    logger.info(f"Forbidden words for group {test_group_id}: {words}")
    remove_forbidden_word(db_session, test_group_id, "spam")
    words_after_removal = get_forbidden_words(db_session, test_group_id)
    logger.info(f"Forbidden words after removal for group {test_group_id}: {words_after_removal}")

    # Example: Test UserFloodRecord
    test_user_id = 67890
    flood_record = get_or_create_user_flood_record(db_session, test_group_id, test_user_id)
    if flood_record:
        logger.info(f"Flood record for user {test_user_id} in group {test_group_id}: {flood_record}")
        update_user_flood_record(db_session, test_group_id, test_user_id, new_timestamp=True, increment_infraction=True)
        updated_flood_record = get_or_create_user_flood_record(db_session, test_group_id, test_user_id)
        logger.info(f"Updated flood record: {updated_flood_record}")
        reset_user_infraction_count(db_session, test_group_id, test_user_id)
        reset_flood_record = get_or_create_user_flood_record(db_session, test_group_id, test_user_id)
        logger.info(f"Reset flood record: {reset_flood_record}")

    db_session.close()
    logger.info("CRUD operations test script finished.")
