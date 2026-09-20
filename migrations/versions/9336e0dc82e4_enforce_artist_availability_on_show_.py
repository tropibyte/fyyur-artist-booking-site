"""enforce artist availability on Show with a trigger

"A show must fall inside one of the artist's published availability windows" is
a cross-row rule: it depends on other rows in another table, which a row-local
CHECK constraint cannot see.  Postgres' answer is a trigger.

Without this the rule lives only in ``ShowForm``, so anything that writes a Show
another way -- a script, a fixture, a psql session, a second process racing the
first -- bypasses it entirely.  With it, the database is the authority and the
form is the friendly error message.

The trigger deliberately mirrors ``Artist.is_available_at``: an artist who has
published *no* windows is bookable at any time, so introducing the feature does
not make every existing artist unbookable.

Known gaps, which are acceptable here but should not be mistaken for coverage:
deleting an Availability window does not retract shows already booked inside it
(a confirmed booking outranks the advisory calendar), and a window deleted
concurrently with a booking can interleave.

Revision ID: 9336e0dc82e4
Revises: ad1a43b4c107
Create Date: 2026-09-20 18:51:47.911469

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9336e0dc82e4'
down_revision = 'ad1a43b4c107'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION fyyur_show_within_availability() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM "Availability" a
                        WHERE a.artist_id = NEW.artist_id)
               AND NOT EXISTS (SELECT 1 FROM "Availability" a
                                WHERE a.artist_id = NEW.artist_id
                                  AND NEW.start_time BETWEEN a.start_time
                                                         AND a.end_time)
            THEN
                RAISE EXCEPTION
                    'artist % is not available at %', NEW.artist_id, NEW.start_time
                    USING ERRCODE = 'check_violation',
                          CONSTRAINT = 'ck_show_within_availability';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_show_within_availability
        BEFORE INSERT OR UPDATE OF artist_id, start_time ON "Show"
        FOR EACH ROW EXECUTE FUNCTION fyyur_show_within_availability();
    """)


def downgrade():
    op.execute('DROP TRIGGER IF EXISTS trg_show_within_availability ON "Show"')
    op.execute('DROP FUNCTION IF EXISTS fyyur_show_within_availability()')
