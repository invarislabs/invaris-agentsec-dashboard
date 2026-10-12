from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import database_url, engine_options
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

URL = database_url()      # same normalisation as the app (postgres:// from Fly.io, Render, ...)


def run_offline() -> None:
    context.configure(url=URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = create_engine(URL, **engine_options(URL))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
