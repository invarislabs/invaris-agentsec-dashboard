"""The Alembic migrations build exactly the schema the models describe (Postgres only)."""
import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text

URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL.startswith("postgresql"), reason="set TEST_DATABASE_URL to a Postgres database")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_migrations_match_the_models(monkeypatch):
    from app.models import Base
    engine = create_engine(URL)
    with engine.begin() as conn:
        conn.execute(text("drop schema public cascade; create schema public"))
    monkeypatch.setenv("DATABASE_URL", URL)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "migrations"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
    command.downgrade(cfg, "base")
    engine.dispose()
