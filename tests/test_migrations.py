"""The Alembic migrations build exactly the schema the models describe, and run both ways on both databases."""
import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

URL = os.environ.get("TEST_DATABASE_URL", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
needs_postgres = pytest.mark.skipif(not URL.startswith("postgresql"), reason="set TEST_DATABASE_URL to a Postgres database")


def _config() -> Config:
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "migrations"))
    return cfg


def test_migrations_have_a_single_head():
    """Two branches that each add a migration on the same parent merge cleanly in Git but leave Alembic with two
    heads, and `alembic upgrade head` (run on every deploy) then refuses to start."""
    heads = ScriptDirectory.from_config(_config()).get_heads()
    assert len(heads) == 1, "several Alembic heads %s: run `alembic merge heads` or rebase the newer migration" % heads


def test_migrations_upgrade_and_downgrade_on_sqlite(tmp_path, monkeypatch):
    url = "sqlite:///%s" % (tmp_path / "migrations.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("DATABASE_DIRECT_URL", raising=False)
    cfg = _config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(url)
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
    command.upgrade(cfg, "head")


@needs_postgres
def test_migrations_match_the_models(monkeypatch):
    from app.models import Base
    engine = create_engine(URL)
    with engine.begin() as conn:
        conn.execute(text("drop schema public cascade; create schema public"))
    monkeypatch.setenv("DATABASE_URL", URL)
    monkeypatch.delenv("DATABASE_DIRECT_URL", raising=False)
    cfg = _config()
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
    command.downgrade(cfg, "base")
    engine.dispose()
