"""Test fixtures.

The suite runs against a real PostgreSQL database (`fyyur_test` by default,
overridable with TEST_DATABASE_URL) rather than SQLite, because most of what is
worth testing here -- CHECK constraints, ON DELETE CASCADE, ILIKE, FILTER
aggregates, a plpgsql trigger -- behaves differently or does not exist at all
on another engine.

The schema is built by running the migration chain, not by `create_all()`.
Three things in this schema exist only in migrations -- the pg_trgm extension,
the expression indexes, and `trg_show_within_availability` -- so `create_all()`
would quietly test a database the application never actually runs against.
"""

import os
import sys

import pytest
from flask_migrate import upgrade as alembic_upgrade
from sqlalchemy import text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app  # noqa: E402
from extensions import db as _db  # noqa: E402
from seed import seed_all  # noqa: E402


@pytest.fixture(scope='session')
def app():
    """One application, one migrated schema, for the whole session."""
    application = create_app('testing')
    with application.app_context():
        # Start from nothing: this also clears alembic_version, the extension
        # and the trigger, so the migration chain runs from zero every time.
        _db.session.execute(text('DROP SCHEMA IF EXISTS public CASCADE'))
        _db.session.execute(text('CREATE SCHEMA public'))
        _db.session.commit()

        alembic_upgrade(directory=os.path.join(BASE_DIR, 'migrations'))

        yield application

        _db.session.remove()


@pytest.fixture()
def db(app):
    """The session-bound SQLAlchemy handle, rolled back after each test."""
    yield _db
    _db.session.rollback()
    _db.session.remove()


@pytest.fixture()
def seeded(db):
    """A freshly seeded catalogue: venues 1-3, artists 4-6, five shows."""
    seed_all(reset=True)
    return db


@pytest.fixture()
def client(app, seeded):
    """Test client over the seeded catalogue."""
    return app.test_client()


@pytest.fixture()
def empty_client(app, db):
    """Test client over an empty catalogue (the genre vocabulary remains)."""
    from seed import reset_data

    reset_data()
    return app.test_client()
