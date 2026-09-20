"""Test fixtures.

The suite runs against a real PostgreSQL database (`fyyur_test` by default,
overridable with TEST_DATABASE_URL) rather than SQLite, because most of what is
worth testing here -- CHECK constraints, ON DELETE CASCADE, ILIKE, FILTER
aggregates -- behaves differently or not at all on another engine.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from extensions import db as _db  # noqa: E402
from seed import seed_all  # noqa: E402


@pytest.fixture(scope='session')
def app():
    """One application, one schema, for the whole session."""
    application = create_app('testing')
    with application.app_context():
        _db.drop_all()
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


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
    """Test client over an empty catalogue (genres only)."""
    from seed import reset_data, seed_genres

    seed_genres()
    reset_data()
    return app.test_client()
