"""search indexes via pg_trgm, seed genre vocabulary

Two changes autogenerate cannot make for you:

1. The original b-tree indexes on ``lower(name)`` could never serve the search.
   Every search runs ``ILIKE '%term%'``, which compiles to the ``~~*`` operator,
   and no b-tree answers a leading wildcard -- ``EXPLAIN`` shows a sequential
   scan even with ``enable_seqscan = off``.  A trigram GIN index does answer it.
   The ``(city, state)`` indexes become ``(state, lower(city))``, matching the
   "City, ST" query now that it uses lowered equality instead of ILIKE.

2. The ``Genre`` table is populated here rather than on first use, so a database
   that has only had ``flask db upgrade`` run against it accepts a new venue or
   artist immediately, without ``flask seed``.

The genre list is written out as literals on purpose: a migration must describe
the schema as of *this* revision, so importing ``constants.GENRES`` would make
an old revision silently change meaning when the application's list changes.

Revision ID: ad1a43b4c107
Revises: 60bf9711705f
Create Date: 2026-09-20 18:51:45.911560

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ad1a43b4c107'
down_revision = '60bf9711705f'
branch_labels = None
depends_on = None

# Frozen copy of constants.GENRES as of this revision.
GENRES = (
    'Alternative', 'Blues', 'Classical', 'Country', 'Electronic', 'Folk',
    'Funk', 'Hip-Hop', 'Heavy Metal', 'Instrumental', 'Jazz',
    'Musical Theatre', 'Pop', 'Punk', 'R&B', 'Reggae', 'Rock n Roll', 'Soul',
    'Swing', 'Other',
)

genre_table = sa.table('Genre', sa.column('name', sa.String))


def upgrade():
    # pg_trgm is a trusted extension from PostgreSQL 13 on, so the database
    # owner can install it without being a superuser.
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    op.drop_index('ix_venue_name_lower', table_name='Venue')
    op.drop_index('ix_venue_city_state', table_name='Venue')
    op.drop_index('ix_artist_name_lower', table_name='Artist')
    op.drop_index('ix_artist_city_state', table_name='Artist')

    op.create_index('ix_venue_name_trgm', 'Venue', ['name'],
                    postgresql_using='gin',
                    postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('ix_venue_city_trgm', 'Venue', ['city'],
                    postgresql_using='gin',
                    postgresql_ops={'city': 'gin_trgm_ops'})
    op.create_index('ix_artist_name_trgm', 'Artist', ['name'],
                    postgresql_using='gin',
                    postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('ix_artist_city_trgm', 'Artist', ['city'],
                    postgresql_using='gin',
                    postgresql_ops={'city': 'gin_trgm_ops'})

    # Expression indexes: op.create_index cannot express `lower(city)`.
    op.execute('CREATE INDEX ix_venue_state_city_lower '
               'ON "Venue" (state, lower(city))')
    op.execute('CREATE INDEX ix_artist_state_city_lower '
               'ON "Artist" (state, lower(city))')

    # Seed the closed vocabulary. ON CONFLICT keeps this safe on a database
    # where `flask seed-genres` already inserted some of them.
    op.execute(
        postgresql.insert(genre_table)
        .values([{'name': name} for name in GENRES])
        .on_conflict_do_nothing(index_elements=['name'])
    )


def downgrade():
    # Only remove genres nothing points at; a genre still in use is real data,
    # and ON DELETE RESTRICT would refuse to drop it anyway.
    op.execute("""
        DELETE FROM "Genre" g
         WHERE NOT EXISTS (SELECT 1 FROM "VenueGenre" vg WHERE vg.genre_id = g.id)
           AND NOT EXISTS (SELECT 1 FROM "ArtistGenre" ag WHERE ag.genre_id = g.id)
    """)

    op.execute('DROP INDEX IF EXISTS ix_artist_state_city_lower')
    op.execute('DROP INDEX IF EXISTS ix_venue_state_city_lower')
    op.drop_index('ix_artist_city_trgm', table_name='Artist')
    op.drop_index('ix_artist_name_trgm', table_name='Artist')
    op.drop_index('ix_venue_city_trgm', table_name='Venue')
    op.drop_index('ix_venue_name_trgm', table_name='Venue')

    op.create_index('ix_artist_city_state', 'Artist', ['city', 'state'])
    op.execute('CREATE INDEX ix_artist_name_lower ON "Artist" (lower(name))')
    op.create_index('ix_venue_city_state', 'Venue', ['city', 'state'])
    op.execute('CREATE INDEX ix_venue_name_lower ON "Venue" (lower(name))')

    op.execute('DROP EXTENSION IF EXISTS pg_trgm')
