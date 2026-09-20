"""Demo data.

Run with `flask seed`.  The venues, artists and shows reproduce the mock data
the starter code used to hard-code -- same names, same IDs (/venues/1,
/artists/4), same show times -- so the finished app can be compared
side-by-side with the original.  Availability windows and the discography are
additions that exercise the stand-out features.
"""

from datetime import datetime, timezone

from sqlalchemy import text

from constants import GENRES
from extensions import db
from models import Album, Artist, Availability, Genre, Show, Song, Venue


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


VENUES = [
    {
        'id': 1,
        'name': 'The Musical Hop',
        'genres': ['Jazz', 'Reggae', 'Swing', 'Classical', 'Folk'],
        'address': '1015 Folsom Street',
        'city': 'San Francisco',
        'state': 'CA',
        'phone': '123-123-1234',
        'website_link': 'https://www.themusicalhop.com',
        'facebook_link': 'https://www.facebook.com/TheMusicalHop',
        'seeking_talent': True,
        'seeking_description': 'We are on the lookout for a local artist to '
                               'play every two weeks. Please call us.',
        'image_link': 'https://images.unsplash.com/photo-1543900694-133f37abaaa5'
                      '?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format'
                      '&fit=crop&w=400&q=60',
    },
    {
        'id': 2,
        'name': 'The Dueling Pianos Bar',
        'genres': ['Classical', 'R&B', 'Hip-Hop'],
        'address': '335 Delancey Street',
        'city': 'New York',
        'state': 'NY',
        'phone': '914-003-1132',
        'website_link': 'https://www.theduelingpianos.com',
        'facebook_link': 'https://www.facebook.com/theduelingpianos',
        'seeking_talent': False,
        'seeking_description': None,
        'image_link': 'https://images.unsplash.com/photo-1497032205916-ac775f0649ae'
                      '?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format'
                      '&fit=crop&w=750&q=80',
    },
    {
        'id': 3,
        'name': 'Park Square Live Music & Coffee',
        'genres': ['Rock n Roll', 'Jazz', 'Classical', 'Folk'],
        'address': '34 Whiskey Moore Ave',
        'city': 'San Francisco',
        'state': 'CA',
        'phone': '415-000-1234',
        'website_link': 'https://www.parksquarelivemusicandcoffee.com',
        'facebook_link': 'https://www.facebook.com/ParkSquareLiveMusicAndCoffee',
        'seeking_talent': False,
        'seeking_description': None,
        'image_link': 'https://images.unsplash.com/photo-1485686531765-ba63b07845a7'
                      '?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format'
                      '&fit=crop&w=747&q=80',
    },
]

ARTISTS = [
    {
        'id': 4,
        'name': 'Guns N Petals',
        'genres': ['Rock n Roll'],
        'city': 'San Francisco',
        'state': 'CA',
        'phone': '326-123-5000',
        'website_link': 'https://www.gunsnpetalsband.com',
        'facebook_link': 'https://www.facebook.com/GunsNPetals',
        'seeking_venue': True,
        'seeking_description': 'Looking for shows to perform at in the '
                               'San Francisco Bay Area!',
        'image_link': 'https://images.unsplash.com/photo-1549213783-8284d0336c4f'
                      '?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format'
                      '&fit=crop&w=300&q=80',
    },
    {
        'id': 5,
        'name': 'Matt Quevedo',
        'genres': ['Jazz'],
        'city': 'New York',
        'state': 'NY',
        'phone': '300-400-5000',
        'website_link': None,
        'facebook_link': 'https://www.facebook.com/mattquevedo923251523',
        'seeking_venue': False,
        'seeking_description': None,
        'image_link': 'https://images.unsplash.com/photo-1495223153807-b916f75de8c5'
                      '?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format'
                      '&fit=crop&w=334&q=80',
    },
    {
        'id': 6,
        'name': 'The Wild Sax Band',
        'genres': ['Jazz', 'Classical'],
        'city': 'San Francisco',
        'state': 'CA',
        'phone': '432-325-5432',
        'website_link': None,
        'facebook_link': None,
        'seeking_venue': False,
        'seeking_description': None,
        'image_link': 'https://images.unsplash.com/photo-1558369981-f9ca78462e61'
                      '?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format'
                      '&fit=crop&w=794&q=80',
    },
]

SHOWS = [
    {'venue_id': 1, 'artist_id': 4, 'start_time': _utc(2019, 5, 21, 21, 30)},
    {'venue_id': 3, 'artist_id': 5, 'start_time': _utc(2019, 6, 15, 23, 0)},
    {'venue_id': 3, 'artist_id': 6, 'start_time': _utc(2035, 4, 1, 20, 0)},
    {'venue_id': 3, 'artist_id': 6, 'start_time': _utc(2035, 4, 8, 20, 0)},
    {'venue_id': 3, 'artist_id': 6, 'start_time': _utc(2035, 4, 15, 20, 0)},
]

# Guns N Petals takes bookings in three windows; The Wild Sax Band's window
# covers its three booked dates.  Matt Quevedo publishes nothing, which means
# "always bookable".
#
# The first window is historical: it covers the 2019 show Guns N Petals already
# played.  Since `trg_show_within_availability` enforces the rule in the
# database, the seeded catalogue has to satisfy it rather than rely on being
# inserted before the windows exist.
AVAILABILITY = [
    {'artist_id': 4, 'start_time': _utc(2019, 5, 21, 18, 0),
     'end_time': _utc(2019, 5, 22, 2, 0)},
    {'artist_id': 4, 'start_time': _utc(2035, 1, 5, 18, 0),
     'end_time': _utc(2035, 1, 5, 23, 59)},
    {'artist_id': 4, 'start_time': _utc(2035, 2, 2, 18, 0),
     'end_time': _utc(2035, 2, 2, 23, 59)},
    {'artist_id': 6, 'start_time': _utc(2035, 4, 1, 0, 0),
     'end_time': _utc(2035, 4, 16, 0, 0)},
]

ALBUMS = [
    {
        'artist_id': 4,
        'name': 'Petals & Pistols',
        'release_year': 2018,
        'image_link': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4'
                      '?auto=format&fit=crop&w=400&q=60',
        'songs': [
            ('Thorns on Sunset', 1, 243),
            ('Bay Bridge Burnout', 2, 198),
            ('Petal to the Metal', 3, 221),
            ('Fog Machine Heart', 4, 305),
        ],
    },
    {
        'artist_id': 5,
        'name': 'Blue Line Sessions',
        'release_year': 2021,
        'image_link': 'https://images.unsplash.com/photo-1511192336575-5a79af67a629'
                      '?auto=format&fit=crop&w=400&q=60',
        'songs': [
            ('Delancey After Midnight', 1, 412),
            ('Uptown Waltz', 2, 276),
            ('Quiet Car', 3, 351),
        ],
    },
    {
        'artist_id': 6,
        'name': 'Brass Tactics',
        'release_year': 2023,
        'image_link': 'https://images.unsplash.com/photo-1514320291840-2e0a9bf2a9ae'
                      '?auto=format&fit=crop&w=400&q=60',
        'songs': [
            ('Reed All About It', 1, 187),
            ('Whiskey Moore Stomp', 2, 264),
            ('Seven Sharps', 3, 233),
            ('Last Call Lullaby', 4, 388),
        ],
    },
]


def seed_genres():
    """Insert any missing rows in the Genre lookup table. Idempotent."""
    existing = {genre.name for genre in db.session.scalars(db.select(Genre))}
    for name in GENRES:
        if name not in existing:
            db.session.add(Genre(name=name))
    db.session.commit()
    return db.session.scalar(db.select(db.func.count()).select_from(Genre))


def reset_data():
    """Delete every row except the genre vocabulary.

    Deletes are ordered children-first.  The junction tables and Song rows go
    with their parents through ON DELETE CASCADE.
    """
    for model in (Show, Availability, Song, Album, Artist, Venue):
        db.session.execute(db.delete(model))
    db.session.commit()


def _restart_sequences():
    """Point each identity sequence past the highest explicit id.

    The demo rows carry hard-coded ids so the URLs match the project brief.
    Without this, the next form submission would try to reuse id 1 and fail on
    the primary key.
    """
    for table in ('Venue', 'Artist', 'Show', 'Availability', 'Album', 'Song',
                  'Genre'):
        db.session.execute(text(
            'SELECT setval(pg_get_serial_sequence(\'"{table}"\', \'id\'), '
            'COALESCE((SELECT MAX(id) FROM "{table}"), 0) + 1, false)'
            .format(table=table)
        ))
    db.session.commit()


def seed_all(reset=True):
    """Load the demo catalogue and return a per-table row count."""
    seed_genres()
    if reset:
        reset_data()

    genres = {genre.name: genre
              for genre in db.session.scalars(db.select(Genre))}

    for record in VENUES:
        data = dict(record)
        names = data.pop('genres')
        venue = Venue(**data)
        venue.genres = [genres[name] for name in names]
        db.session.add(venue)

    for record in ARTISTS:
        data = dict(record)
        names = data.pop('genres')
        artist = Artist(**data)
        artist.genres = [genres[name] for name in names]
        db.session.add(artist)

    db.session.flush()  # artists and venues need ids before shows reference them

    # Availability first: `trg_show_within_availability` checks each Show
    # against the windows that exist at insert time, so seeding the windows
    # afterwards would let the shows through unchecked.
    for record in AVAILABILITY:
        db.session.add(Availability(**record))
    db.session.flush()

    for record in SHOWS:
        db.session.add(Show(**record))

    for record in ALBUMS:
        data = dict(record)
        songs = data.pop('songs')
        album = Album(**data)
        album.songs = [
            Song(title=title, track_number=number, duration_seconds=seconds)
            for title, number, seconds in songs
        ]
        db.session.add(album)

    db.session.commit()
    _restart_sequences()

    return {
        'genres': db.session.scalar(db.select(db.func.count()).select_from(Genre)),
        'venues': db.session.scalar(db.select(db.func.count()).select_from(Venue)),
        'artists': db.session.scalar(db.select(db.func.count()).select_from(Artist)),
        'shows': db.session.scalar(db.select(db.func.count()).select_from(Show)),
        'availability': db.session.scalar(
            db.select(db.func.count()).select_from(Availability)),
        'albums': db.session.scalar(db.select(db.func.count()).select_from(Album)),
        'songs': db.session.scalar(db.select(db.func.count()).select_from(Song)),
    }
