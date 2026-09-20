"""Data models for Fyyur.

Schema at a glance (see ``docs/SCHEMA.md`` for the normalisation argument and
the full ER diagram):

    Artist 1 --- * Show * --- 1 Venue      many-to-many, expressed as an
                                           association object because the
                                           booking carries its own attribute
                                           (start_time)
    Artist * --- * Genre                   via the ArtistGenre junction table
    Venue  * --- * Genre                   via the VenueGenre junction table
    Artist 1 --- * Availability            bookable windows
    Artist 1 --- * Album 1 --- * Song      discography

Query helpers live on the models rather than in the controllers: a controller
should say *what* it wants ("venues grouped by area"), not spell out the join
that produces it.  Each helper returns plain dicts in exactly the shape the
templates already expect, so the view layer stays a one-liner.
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func, text

from constants import GENRES, US_STATES
from extensions import db


def utcnow():
    """Timezone-aware 'now'.

    Every timestamp column is TIMESTAMP WITH TIME ZONE, so the Python side has
    to be aware as well; mixing naive and aware datetimes is the classic way to
    get a comparison that is silently wrong by the UTC offset.
    """
    return datetime.now(timezone.utc)


def _iso(value):
    """Render a datetime the way the templates' ``datetime`` filter expects."""
    return value.isoformat() if value is not None else None


# ---------------------------------------------------------------------------#
# Junction tables
#
# Genres are a many-to-many relationship, not a column.  Storing them as a
# comma-separated string (or even as a Postgres ARRAY) would repeat a group of
# values inside a single field -- that breaks first normal form and turns
# "every venue tagged Jazz" into an unindexable substring scan instead of a
# join against an indexed key.
# ---------------------------------------------------------------------------#

venue_genres = db.Table(
    'VenueGenre',
    db.Column('venue_id', db.Integer,
              ForeignKey('Venue.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer,
              ForeignKey('Genre.id', ondelete='RESTRICT'), primary_key=True),
)

artist_genres = db.Table(
    'ArtistGenre',
    db.Column('artist_id', db.Integer,
              ForeignKey('Artist.id', ondelete='CASCADE'), primary_key=True),
    db.Column('genre_id', db.Integer,
              ForeignKey('Genre.id', ondelete='RESTRICT'), primary_key=True),
)


class Genre(db.Model):
    """A closed vocabulary of musical genres, seeded from ``constants.GENRES``."""

    __tablename__ = 'Genre'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)

    venues = db.relationship('Venue', secondary=venue_genres,
                             back_populates='genres')
    artists = db.relationship('Artist', secondary=artist_genres,
                              back_populates='genres')

    __table_args__ = (
        CheckConstraint("name IN {}".format(GENRES), name='ck_genre_name_allowed'),
    )

    def __repr__(self):
        return '<Genre {}>'.format(self.name)

    @staticmethod
    def resolve(names):
        """Map genre names to ``Genre`` rows, creating any that are missing.

        One SELECT for the whole list rather than one per name.
        """
        wanted = [name for name in dict.fromkeys(names or []) if name]
        if not wanted:
            return []

        existing = {
            genre.name: genre
            for genre in db.session.scalars(
                db.select(Genre).where(Genre.name.in_(wanted))
            )
        }

        resolved = []
        for name in wanted:
            genre = existing.get(name)
            if genre is None:
                genre = Genre(name=name)
                db.session.add(genre)
            resolved.append(genre)
        return resolved


# ---------------------------------------------------------------------------#
# Mixins
# ---------------------------------------------------------------------------#

class TimestampMixin:
    """``created_at`` / ``updated_at``, defaulted by the database."""

    created_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           server_default=func.now(), default=utcnow,
                           index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False,
                           server_default=func.now(), default=utcnow,
                           onupdate=utcnow)


class ContactMixin:
    """Columns shared by the two listable entities, Venue and Artist."""

    name = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    # Two-letter USPS code, constrained to the canonical list at the database
    # level.  A CHECK constraint is preferred over a native Postgres ENUM here
    # because adding a code later is a one-line migration instead of an
    # ALTER TYPE, which cannot run inside a transaction block.
    state = db.Column(db.String(2), nullable=False)
    phone = db.Column(db.String(20))
    image_link = db.Column(db.String(500))
    facebook_link = db.Column(db.String(120))
    website_link = db.Column(db.String(120))
    seeking_description = db.Column(db.Text)


# ---------------------------------------------------------------------------#
# Venue
# ---------------------------------------------------------------------------#

class Venue(ContactMixin, TimestampMixin, db.Model):
    __tablename__ = 'Venue'

    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(120), nullable=False)
    seeking_talent = db.Column(db.Boolean, nullable=False,
                               default=False, server_default='false')

    genres = db.relationship('Genre', secondary=venue_genres,
                             back_populates='venues',
                             order_by='Genre.name', lazy='selectin')
    # A venue owns its bookings: deleting the venue deletes its shows, in the
    # database (ON DELETE CASCADE) as well as in the session.
    shows = db.relationship('Show', back_populates='venue',
                            cascade='all, delete-orphan',
                            passive_deletes=True)
    # Read-only view of the far side of the many-to-many.
    artists = db.relationship('Artist', secondary='Show', viewonly=True)

    __table_args__ = (
        # No two listings for the same room at the same address.
        UniqueConstraint('name', 'address', 'city', 'state',
                         name='uq_venue_name_address'),
        CheckConstraint("state IN {}".format(US_STATES), name='ck_venue_state'),
        CheckConstraint("length(trim(name)) > 0", name='ck_venue_name_present'),
        # A venue that says it is seeking talent has to say what for.
        CheckConstraint('NOT seeking_talent OR seeking_description IS NOT NULL',
                        name='ck_venue_seeking_description'),
        # Case-insensitive search uses this index instead of scanning.
        Index('ix_venue_name_lower', text('lower(name)')),
        Index('ix_venue_city_state', 'city', 'state'),
    )

    def __repr__(self):
        return '<Venue {} {}>'.format(self.id, self.name)

    # -- writes -------------------------------------------------------------#

    def apply_form(self, form):
        """Copy validated form data onto the record (used by create and edit)."""
        self.name = form.name.data.strip()
        self.city = form.city.data.strip()
        self.state = form.state.data
        self.address = form.address.data.strip()
        self.phone = (form.phone.data or '').strip() or None
        self.image_link = (form.image_link.data or '').strip() or None
        self.facebook_link = (form.facebook_link.data or '').strip() or None
        self.website_link = (form.website_link.data or '').strip() or None
        self.seeking_talent = bool(form.seeking_talent.data)
        description = (form.seeking_description.data or '').strip() or None
        self.seeking_description = description if self.seeking_talent else None
        self.genres = Genre.resolve(form.genres.data)
        return self

    # -- detail page --------------------------------------------------------#

    def shows_by_period(self):
        """Return ``(past, upcoming)`` show dicts for this venue's page.

        One JOIN against Artist, split in Python against a single ``now`` so a
        show cannot land in both lists (or in neither) because the clock moved
        between two queries.

        SQL: SELECT ... FROM "Show"
             JOIN "Artist" ON "Artist".id = "Show".artist_id
             WHERE "Show".venue_id = :id
             ORDER BY "Show".start_time
        """
        now = utcnow()
        rows = db.session.execute(
            db.select(Show, Artist)
            .join(Artist, Show.artist_id == Artist.id)
            .where(Show.venue_id == self.id)
            .order_by(Show.start_time)
        ).all()

        past, upcoming = [], []
        for show, artist in rows:
            entry = {
                'artist_id': artist.id,
                'artist_name': artist.name,
                'artist_image_link': artist.image_link,
                'start_time': _iso(show.start_time),
            }
            (upcoming if show.start_time >= now else past).append(entry)
        past.reverse()  # most recent performance first
        return past, upcoming

    def to_detail_dict(self):
        """The exact payload ``pages/show_venue.html`` consumes."""
        past, upcoming = self.shows_by_period()
        return {
            'id': self.id,
            'name': self.name,
            'genres': [genre.name for genre in self.genres],
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'phone': self.phone,
            'website': self.website_link,
            'facebook_link': self.facebook_link,
            'seeking_talent': self.seeking_talent,
            'seeking_description': self.seeking_description,
            'image_link': self.image_link,
            'past_shows': past,
            'upcoming_shows': upcoming,
            'past_shows_count': len(past),
            'upcoming_shows_count': len(upcoming),
        }

    # -- collection queries -------------------------------------------------#

    @staticmethod
    def _listing_select():
        """Venue rows plus a count of their upcoming shows.

        SQL: SELECT "Venue".id, "Venue".name, "Venue".city, "Venue".state,
                    count("Show".id) FILTER (WHERE "Show".start_time >= :now)
             FROM "Venue" LEFT OUTER JOIN "Show" ON "Show".venue_id = "Venue".id
             GROUP BY "Venue".id
        """
        upcoming = func.count(Show.id).filter(Show.start_time >= utcnow())
        return (
            db.select(Venue.id, Venue.name, Venue.city, Venue.state,
                      upcoming.label('num_upcoming_shows'))
            .outerjoin(Show, Show.venue_id == Venue.id)
            .group_by(Venue.id)
        )

    @classmethod
    def grouped_by_area(cls):
        """``[{city, state, venues: [{id, name, num_upcoming_shows}]}]``.

        A single grouped query feeds the whole page; no per-venue count query.
        """
        rows = db.session.execute(
            cls._listing_select().order_by(Venue.state, Venue.city, Venue.name)
        ).all()

        areas, index = [], {}
        for venue_id, name, city, state, num_upcoming in rows:
            key = (city, state)
            if key not in index:
                index[key] = {'city': city, 'state': state, 'venues': []}
                areas.append(index[key])
            index[key]['venues'].append({
                'id': venue_id,
                'name': name,
                'num_upcoming_shows': num_upcoming,
            })
        return areas

    @classmethod
    def search(cls, term):
        """Case-insensitive partial search by name/city, or by "City, ST"."""
        city, state = parse_city_state(term)
        statement = cls._listing_select()

        if city is not None:
            statement = statement.where(Venue.city.ilike(city),
                                        Venue.state == state)
        elif state is not None:
            statement = statement.where(Venue.state == state)
        else:
            pattern = '%{}%'.format((term or '').strip())
            statement = statement.where(
                db.or_(Venue.name.ilike(pattern), Venue.city.ilike(pattern))
            )

        rows = db.session.execute(statement.order_by(Venue.name)).all()
        return {
            'count': len(rows),
            'data': [
                {'id': row.id, 'name': row.name,
                 'num_upcoming_shows': row.num_upcoming_shows}
                for row in rows
            ],
        }

    @classmethod
    def listing(cls):
        """``[{id, name}]`` for the booking form's venue picker."""
        rows = db.session.execute(
            db.select(Venue.id, Venue.name).order_by(Venue.name)
        ).all()
        return [{'id': row.id, 'name': row.name} for row in rows]

    @classmethod
    def recent(cls, limit=10):
        """Newest listings first, for the home page."""
        return db.session.scalars(
            db.select(Venue)
            .order_by(Venue.created_at.desc(), Venue.id.desc())
            .limit(limit)
        ).all()


# ---------------------------------------------------------------------------#
# Artist
# ---------------------------------------------------------------------------#

class Artist(ContactMixin, TimestampMixin, db.Model):
    __tablename__ = 'Artist'

    id = db.Column(db.Integer, primary_key=True)
    seeking_venue = db.Column(db.Boolean, nullable=False,
                              default=False, server_default='false')

    genres = db.relationship('Genre', secondary=artist_genres,
                             back_populates='artists',
                             order_by='Genre.name', lazy='selectin')
    shows = db.relationship('Show', back_populates='artist',
                            cascade='all, delete-orphan',
                            passive_deletes=True)
    venues = db.relationship('Venue', secondary='Show', viewonly=True)
    availabilities = db.relationship('Availability', back_populates='artist',
                                     cascade='all, delete-orphan',
                                     passive_deletes=True,
                                     order_by='Availability.start_time',
                                     lazy='selectin')
    albums = db.relationship('Album', back_populates='artist',
                             cascade='all, delete-orphan',
                             passive_deletes=True,
                             order_by='Album.name')

    __table_args__ = (
        # Two acts may share a name in different towns, but not in one town.
        UniqueConstraint('name', 'city', 'state', name='uq_artist_name_city'),
        CheckConstraint("state IN {}".format(US_STATES), name='ck_artist_state'),
        CheckConstraint("length(trim(name)) > 0", name='ck_artist_name_present'),
        CheckConstraint('NOT seeking_venue OR seeking_description IS NOT NULL',
                        name='ck_artist_seeking_description'),
        Index('ix_artist_name_lower', text('lower(name)')),
        Index('ix_artist_city_state', 'city', 'state'),
    )

    def __repr__(self):
        return '<Artist {} {}>'.format(self.id, self.name)

    # -- writes -------------------------------------------------------------#

    def apply_form(self, form):
        self.name = form.name.data.strip()
        self.city = form.city.data.strip()
        self.state = form.state.data
        self.phone = (form.phone.data or '').strip() or None
        self.image_link = (form.image_link.data or '').strip() or None
        self.facebook_link = (form.facebook_link.data or '').strip() or None
        self.website_link = (form.website_link.data or '').strip() or None
        self.seeking_venue = bool(form.seeking_venue.data)
        description = (form.seeking_description.data or '').strip() or None
        self.seeking_description = description if self.seeking_venue else None
        self.genres = Genre.resolve(form.genres.data)
        return self

    # -- availability -------------------------------------------------------#

    def is_available_at(self, when):
        """True when ``when`` falls inside one of this artist's windows.

        An artist who has published no windows is treated as always bookable,
        so introducing the feature does not retroactively make every existing
        artist impossible to book.
        """
        if not self.availabilities:
            return True
        return any(window.covers(when) for window in self.availabilities)

    def availability_summary(self):
        return [window.to_dict() for window in self.availabilities]

    # -- detail page --------------------------------------------------------#

    def shows_by_period(self):
        """``(past, upcoming)`` show dicts, joined against Venue.

        SQL: SELECT ... FROM "Show"
             JOIN "Venue" ON "Venue".id = "Show".venue_id
             WHERE "Show".artist_id = :id
             ORDER BY "Show".start_time
        """
        now = utcnow()
        rows = db.session.execute(
            db.select(Show, Venue)
            .join(Venue, Show.venue_id == Venue.id)
            .where(Show.artist_id == self.id)
            .order_by(Show.start_time)
        ).all()

        past, upcoming = [], []
        for show, venue in rows:
            entry = {
                'venue_id': venue.id,
                'venue_name': venue.name,
                'venue_image_link': venue.image_link,
                'start_time': _iso(show.start_time),
            }
            (upcoming if show.start_time >= now else past).append(entry)
        past.reverse()
        return past, upcoming

    def to_detail_dict(self):
        """The exact payload ``pages/show_artist.html`` consumes."""
        past, upcoming = self.shows_by_period()
        albums = sorted(
            (album.to_dict() for album in self.albums),
            key=lambda album: (-(album['release_year'] or 0), album['name']),
        )
        return {
            'id': self.id,
            'name': self.name,
            'genres': [genre.name for genre in self.genres],
            'city': self.city,
            'state': self.state,
            'phone': self.phone,
            'website': self.website_link,
            'facebook_link': self.facebook_link,
            'seeking_venue': self.seeking_venue,
            'seeking_description': self.seeking_description,
            'image_link': self.image_link,
            'past_shows': past,
            'upcoming_shows': upcoming,
            'past_shows_count': len(past),
            'upcoming_shows_count': len(upcoming),
            # Additions beyond the mock payload; the template renders these
            # sections only when they are non-empty.
            'availability': self.availability_summary(),
            'albums': albums,
        }

    # -- collection queries -------------------------------------------------#

    @staticmethod
    def _listing_select():
        upcoming = func.count(Show.id).filter(Show.start_time >= utcnow())
        return (
            db.select(Artist.id, Artist.name, Artist.city, Artist.state,
                      upcoming.label('num_upcoming_shows'))
            .outerjoin(Show, Show.artist_id == Artist.id)
            .group_by(Artist.id)
        )

    @classmethod
    def listing(cls):
        """``[{id, name}]`` for ``/artists``."""
        rows = db.session.execute(
            db.select(Artist.id, Artist.name).order_by(Artist.name)
        ).all()
        return [{'id': row.id, 'name': row.name} for row in rows]

    @classmethod
    def search(cls, term):
        city, state = parse_city_state(term)
        statement = cls._listing_select()

        if city is not None:
            statement = statement.where(Artist.city.ilike(city),
                                        Artist.state == state)
        elif state is not None:
            statement = statement.where(Artist.state == state)
        else:
            pattern = '%{}%'.format((term or '').strip())
            statement = statement.where(
                db.or_(Artist.name.ilike(pattern), Artist.city.ilike(pattern))
            )

        rows = db.session.execute(statement.order_by(Artist.name)).all()
        return {
            'count': len(rows),
            'data': [
                {'id': row.id, 'name': row.name,
                 'num_upcoming_shows': row.num_upcoming_shows}
                for row in rows
            ],
        }

    @classmethod
    def recent(cls, limit=10):
        return db.session.scalars(
            db.select(Artist)
            .order_by(Artist.created_at.desc(), Artist.id.desc())
            .limit(limit)
        ).all()


# ---------------------------------------------------------------------------#
# Show -- the association object between Artist and Venue
# ---------------------------------------------------------------------------#

class Show(TimestampMixin, db.Model):
    """A booking: one artist, at one venue, at one moment in time.

    Artist and Venue are many-to-many with each other.  The relationship is
    modelled as an association *object* rather than a bare junction table
    because the association carries its own data (``start_time``) and because a
    show is a first-class thing the application lists and links to.
    """

    __tablename__ = 'Show'

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer,
                          ForeignKey('Artist.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    venue_id = db.Column(db.Integer,
                         ForeignKey('Venue.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False,
                           index=True)

    artist = db.relationship('Artist', back_populates='shows')
    venue = db.relationship('Venue', back_populates='shows')

    __table_args__ = (
        # An artist cannot be in two places at once.  This belongs to the
        # database, not the form: two concurrent requests can both pass a
        # Python-side check, but only one can win a unique index.
        UniqueConstraint('artist_id', 'start_time',
                         name='uq_show_artist_start_time'),
    )

    def __repr__(self):
        return '<Show {} artist={} venue={}>'.format(
            self.id, self.artist_id, self.venue_id)

    @property
    def is_upcoming(self):
        return self.start_time >= utcnow()

    @classmethod
    def listing(cls):
        """Every show, newest first, joined to both parents in one query.

        SQL: SELECT ... FROM "Show"
             JOIN "Artist" ON "Artist".id = "Show".artist_id
             JOIN "Venue"  ON "Venue".id  = "Show".venue_id
             ORDER BY "Show".start_time DESC
        """
        rows = db.session.execute(
            db.select(Show, Artist, Venue)
            .join(Artist, Show.artist_id == Artist.id)
            .join(Venue, Show.venue_id == Venue.id)
            .order_by(Show.start_time.desc())
        ).all()
        return [
            {
                'venue_id': venue.id,
                'venue_name': venue.name,
                'artist_id': artist.id,
                'artist_name': artist.name,
                'artist_image_link': artist.image_link,
                'start_time': _iso(show.start_time),
            }
            for show, artist, venue in rows
        ]


# ---------------------------------------------------------------------------#
# Availability -- stand-out feature: artists publish bookable windows
# ---------------------------------------------------------------------------#

class Availability(TimestampMixin, db.Model):
    """A window during which an artist accepts bookings."""

    __tablename__ = 'Availability'

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer,
                          ForeignKey('Artist.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)

    artist = db.relationship('Artist', back_populates='availabilities')

    __table_args__ = (
        CheckConstraint('end_time > start_time', name='ck_availability_order'),
        UniqueConstraint('artist_id', 'start_time', 'end_time',
                         name='uq_availability_window'),
    )

    def covers(self, when):
        return self.start_time <= when <= self.end_time

    def overlaps(self, start, end):
        return self.start_time < end and start < self.end_time

    def to_dict(self):
        return {
            'id': self.id,
            'start_time': _iso(self.start_time),
            'end_time': _iso(self.end_time),
            'is_past': self.end_time < utcnow(),
        }

    def __repr__(self):
        return '<Availability artist={} {}>'.format(self.artist_id,
                                                    self.start_time)


# ---------------------------------------------------------------------------#
# Discography -- stand-out feature: albums and songs on the artist page
# ---------------------------------------------------------------------------#

class Album(TimestampMixin, db.Model):
    __tablename__ = 'Album'

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer,
                          ForeignKey('Artist.id', ondelete='CASCADE'),
                          nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    release_year = db.Column(db.Integer)
    image_link = db.Column(db.String(500))

    artist = db.relationship('Artist', back_populates='albums')
    songs = db.relationship('Song', back_populates='album',
                            cascade='all, delete-orphan',
                            passive_deletes=True,
                            order_by='Song.track_number')

    __table_args__ = (
        UniqueConstraint('artist_id', 'name', name='uq_album_artist_name'),
        # 1877 is the year of the first recorded sound.
        CheckConstraint('release_year IS NULL OR '
                        '(release_year BETWEEN 1877 AND 2100)',
                        name='ck_album_release_year'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'release_year': self.release_year,
            'image_link': self.image_link,
            'songs': [song.to_dict() for song in self.songs],
        }

    def __repr__(self):
        return '<Album {}>'.format(self.name)


class Song(db.Model):
    __tablename__ = 'Song'

    id = db.Column(db.Integer, primary_key=True)
    album_id = db.Column(db.Integer,
                         ForeignKey('Album.id', ondelete='CASCADE'),
                         nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    track_number = db.Column(db.Integer)
    duration_seconds = db.Column(db.Integer)

    album = db.relationship('Album', back_populates='songs')

    __table_args__ = (
        UniqueConstraint('album_id', 'title', name='uq_song_album_title'),
        UniqueConstraint('album_id', 'track_number', name='uq_song_album_track'),
        CheckConstraint('track_number IS NULL OR track_number > 0',
                        name='ck_song_track_number'),
        CheckConstraint('duration_seconds IS NULL OR duration_seconds > 0',
                        name='ck_song_duration'),
    )

    @property
    def duration(self):
        """``m:ss``, or None when the length is unknown."""
        if self.duration_seconds is None:
            return None
        minutes, seconds = divmod(self.duration_seconds, 60)
        return '{}:{:02d}'.format(minutes, seconds)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'track_number': self.track_number,
            'duration': self.duration,
        }

    def __repr__(self):
        return '<Song {}>'.format(self.title)


# ---------------------------------------------------------------------------#
# Shared helpers
# ---------------------------------------------------------------------------#

def parse_city_state(term):
    """Interpret a search term as a place.

    Returns ``(city, state)`` for "San Francisco, CA", ``(None, state)`` for a
    bare "CA", and ``(None, None)`` for anything else -- which the callers
    treat as an ordinary name search.
    """
    if not term:
        return None, None

    cleaned = term.strip()
    if ',' in cleaned:
        city, _, state = cleaned.rpartition(',')
        city, state = city.strip(), state.strip().upper()
        if city and state in US_STATES:
            return city, state
        return None, None

    if len(cleaned) == 2 and cleaned.upper() in US_STATES:
        return None, cleaned.upper()
    return None, None
