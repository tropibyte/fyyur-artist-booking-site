"""Print the PostgreSQL each ORM helper compiles to.

`flask sql-preview` (optionally with a name, e.g. `flask sql-preview search`)
renders the statements in `models.py` through the psycopg2 dialect.  It exists
so the SQL behind the ORM can be read, reviewed and pasted into psql rather
than taken on trust -- and it is what generated `docs/SQL_EQUIVALENTS.md`.
"""

from sqlalchemy.dialects import postgresql

from extensions import db
from models import Artist, Show, Venue


def compile_sql(statement):
    """Render a Core/ORM statement as PostgreSQL text."""
    # `paramstyle='named'` keeps psycopg2's pyformat escaping from doubling
    # every literal percent sign, so an ILIKE pattern reads as '%music%'.
    dialect = postgresql.dialect(paramstyle='named')
    try:
        compiled = statement.compile(
            dialect=dialect, compile_kwargs={'literal_binds': True},
        )
    except (NotImplementedError, TypeError):
        # Some bind types have no literal renderer; keep the placeholders.
        compiled = statement.compile(dialect=dialect)
    return str(compiled)


def previews():
    """`{name: statement}` for every query worth showing."""
    return {
        'venues.grouped_by_area':
            Venue._listing_select().order_by(Venue.state, Venue.city,
                                             Venue.name),
        'venues.search':
            Venue._listing_select()
            .where(db.or_(Venue.name.ilike('%music%'),
                          Venue.city.ilike('%music%')))
            .order_by(Venue.name),
        'venues.search_by_city_state':
            Venue._listing_select()
            .where(db.func.lower(Venue.city) == 'san francisco',
                   Venue.state == 'CA')
            .order_by(Venue.name),
        'venues.shows_by_period':
            db.select(Show, Artist)
            .join(Artist, Show.artist_id == Artist.id)
            .where(Show.venue_id == 1)
            .order_by(Show.start_time),
        'venues.recent':
            db.select(Venue).order_by(Venue.created_at.desc(),
                                      Venue.id.desc()).limit(10),
        'artists.listing':
            db.select(Artist.id, Artist.name).order_by(Artist.name),
        'artists.search':
            Artist._listing_select()
            .where(db.or_(Artist.name.ilike('%band%'),
                          Artist.city.ilike('%band%')))
            .order_by(Artist.name),
        'artists.shows_by_period':
            db.select(Show, Venue)
            .join(Venue, Show.venue_id == Venue.id)
            .where(Show.artist_id == 4)
            .order_by(Show.start_time),
        'shows.listing':
            db.select(Show, Artist, Venue)
            .join(Artist, Show.artist_id == Artist.id)
            .join(Venue, Show.venue_id == Venue.id)
            .order_by(Show.start_time.desc()),
    }


def print_previews(name=None):
    for key, statement in previews().items():
        if name and name not in key:
            continue
        print('-- {}'.format(key))
        print(compile_sql(statement))
        print()
