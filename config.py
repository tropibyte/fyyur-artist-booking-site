"""Application configuration.

Configuration is environment-driven so that the same code runs against a
developer's local Postgres instance, a throwaway test database, or a deployed
instance without edits.  Values are read from the process environment, which
`python-dotenv` populates from the (git-ignored) `.env` file on startup.
"""

import os

from dotenv import load_dotenv

# Grabs the folder where the script runs.
basedir = os.path.abspath(os.path.dirname(__file__))

# Load `.env` before any class body reads os.environ.
load_dotenv(os.path.join(basedir, '.env'))


def _database_url(var_name, default):
    """Return the connection URL in `var_name`, normalised for SQLAlchemy.

    Hosted providers (Heroku, Render) hand out `postgres://` URLs, a scheme
    SQLAlchemy 1.4+ no longer recognises; rewrite it to `postgresql://`.
    """
    url = os.environ.get(var_name) or default
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    """Settings shared by every environment."""

    # Flask-WTF signs its CSRF tokens with this; a fixed value keeps sessions
    # (and therefore open forms) valid across reloads of the dev server.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fyyur-dev-secret-key')

    # Connect to the database.
    #
    # The fallback is the Udacity classroom workspace's setup -- superuser
    # `postgres`, no password, on localhost -- so a reviewer who clones and runs
    # `flask db upgrade` needs no .env and no role creation.  Any other machine
    # sets DATABASE_URL in .env; see .env.example.
    SQLALCHEMY_DATABASE_URI = _database_url(
        'DATABASE_URL',
        'postgresql://postgres@127.0.0.1:5432/fyyur',
    )

    # The event system is only needed by extensions that hook model changes;
    # leaving it on costs memory per session for no benefit here.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Recycle pooled connections before Postgres' own idle timeout can close
    # them, and check liveness on checkout so a restarted server does not
    # surface as a 500 on the next request.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}

    WTF_CSRF_ENABLED = True

    # Number of items on the "recently listed" panels of the home page.
    RECENT_LISTING_LIMIT = 10


class DevelopmentConfig(Config):
    """Local development: debug on, SQL echoed when FYYUR_SQL_ECHO=1."""

    DEBUG = True
    SQLALCHEMY_ECHO = os.environ.get('FYYUR_SQL_ECHO', '0') == '1'


class TestingConfig(Config):
    """Used by the pytest suite against a disposable database."""

    TESTING = True
    DEBUG = False
    # CSRF tokens cannot be produced by the test client, so turn the check off.
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = _database_url(
        'TEST_DATABASE_URL',
        'postgresql://postgres@127.0.0.1:5432/fyyur_test',
    )


class ProductionConfig(Config):
    DEBUG = False


# `create_app()` looks the requested configuration up here by name.
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
