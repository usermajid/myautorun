from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# target_metadata = None

# Corrected: Import Base from your project's models
# and then set target_metadata.
# This assumes your models.py is structured to have a Base object.
from telegram_bot.database.models import Base # Adjust path as necessary
target_metadata = Base.metadata


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_db_url():
    """
    Returns the database URL.
    Tries to load from environment variable DATABASE_URL first,
    then falls back to sqlalchemy.url in alembic.ini.
    """
    from os import getenv
    # Try to get from environment variable (recommended for security)
    url = getenv("DATABASE_URL")
    if url:
        return url
    # Fallback to alembic.ini if not in environment
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # url = config.get_main_option("sqlalchemy.url") # Original
    url = get_db_url() # Use helper to get URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # configuration = config.get_section(config.config_ini_section) # Original
    # configuration["sqlalchemy.url"] = get_db_url() # Set the URL dynamically
    # connectable = engine_from_config(
    #     configuration, # Use the modified configuration
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )
    
    # Simplified approach for online mode using get_db_url()
    db_url = get_db_url()
    if not db_url:
        raise Exception("Database URL is not set. Configure DATABASE_URL environment variable or sqlalchemy.url in alembic.ini.")

    # Create engine configuration dictionary
    engine_config_dict = {
        "url": db_url, # Pass the URL directly
        # Add other engine parameters if needed, e.g., poolclass for NullPool
    }

    connectable = engine_from_config(
        engine_config_dict, # Use the constructed dict
        prefix="", # No prefix needed as we are passing url directly
        poolclass=pool.NullPool,
    )


    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
