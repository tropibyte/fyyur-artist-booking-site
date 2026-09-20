"""Flask-WTF form definitions.

Validation happens on three levels and each one exists for a reason:

1. **HTML attributes** (``required``, ``type="url"``) catch typos before a
   request is even sent.
2. **WTForms validators**, here, reject a bad submission with a readable
   message next to the offending field.
3. **Database constraints** (``models.py``) are the backstop: they hold even
   when two requests race each other, or when a row is inserted by a script
   that never touched these forms.

Level 2 without level 3 is a suggestion, not a rule -- so every rule below has
a counterpart in the schema.
"""

from datetime import timezone

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    FieldList,
    FormField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
)
from wtforms.validators import (
    URL,
    DataRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from constants import GENRE_CHOICES, GENRES, PHONE_REGEX, STATE_CHOICES, US_STATES

# Browsers submit `datetime-local` inputs as "2035-04-01T20:00"; seed data and
# manual entry use "2035-04-01 20:00:00".  Accept all three spellings.
DATETIME_FORMATS = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']


def strip(value):
    """WTForms filter: trim whitespace, turn a blank string into None."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def as_utc(value):
    """Treat a naive form datetime as UTC.

    The browser hands back wall-clock time with no offset.  Anchoring it to UTC
    here keeps it comparable with the TIMESTAMPTZ columns instead of raising
    "can't compare offset-naive and offset-aware datetimes".
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_label(value, fmt='%Y-%m-%d %H:%M'):
    """Format a timestamp as UTC wall-clock for a message.

    Postgres hands `timestamptz` values back in the *session's* timezone, so a
    window stored as 18:00Z arrives as 13:00-05:00. Formatting that directly
    would print "13:00" under a label that says UTC.
    """
    return as_utc(value).strftime(fmt)


def db_get(model, primary_key):
    """``session.get()`` without importing the session into every validator."""
    from extensions import db

    if primary_key is None:
        return None
    return db.session.get(model, primary_key)


class AnyOfMultiple:
    """Every selected value must come from ``choices``.

    ``AnyOf`` validates a single value; a ``SelectMultipleField`` holds a list.
    Without this, a hand-crafted POST could try to store "Polka", and the CHECK
    constraint behind it would surface as a 500 rather than a message.
    """

    def __init__(self, choices, message=None):
        self.choices = set(choices)
        self.message = message

    def __call__(self, form, field):
        invalid = [value for value in (field.data or [])
                   if value not in self.choices]
        if invalid:
            raise ValidationError(
                self.message
                or 'Not a valid choice: {}.'.format(', '.join(invalid))
            )


class _ListingForm(FlaskForm):
    """Fields and rules shared by VenueForm and ArtistForm."""

    name = StringField(
        'name', filters=[strip],
        validators=[DataRequired(message='Name is required.'),
                    Length(max=120)],
    )
    city = StringField(
        'city', filters=[strip],
        validators=[DataRequired(message='City is required.'),
                    Length(max=120)],
    )
    state = SelectField(
        'state',
        validators=[DataRequired(message='State is required.')],
        choices=STATE_CHOICES,
    )
    phone = StringField(
        'phone', filters=[strip],
        validators=[Optional(),
                    Regexp(PHONE_REGEX,
                           message='Phone must look like 555-555-5555.')],
    )
    image_link = StringField(
        'image_link', filters=[strip],
        validators=[Optional(), URL(message='Image link must be a valid URL.'),
                    Length(max=500)],
    )
    facebook_link = StringField(
        'facebook_link', filters=[strip],
        validators=[Optional(),
                    URL(message='Facebook link must be a valid URL.'),
                    Length(max=120)],
    )
    website_link = StringField(
        'website_link', filters=[strip],
        validators=[Optional(), URL(message='Website must be a valid URL.'),
                    Length(max=120)],
    )
    genres = SelectMultipleField(
        'genres',
        validators=[DataRequired(message='Pick at least one genre.'),
                    AnyOfMultiple(GENRES)],
        choices=GENRE_CHOICES,
    )
    seeking_description = TextAreaField('seeking_description', filters=[strip])

    def validate_state(self, field):
        """Keeps the rule next to the data even if choices are ever dynamic."""
        if field.data not in US_STATES:
            raise ValidationError('Not a valid state.')


class VenueForm(_ListingForm):
    address = StringField(
        'address', filters=[strip],
        validators=[DataRequired(message='Address is required.'),
                    Length(max=120)],
    )
    seeking_talent = BooleanField('seeking_talent')

    def validate_seeking_description(self, field):
        """Mirrors the ck_venue_seeking_description CHECK constraint."""
        if self.seeking_talent.data and not field.data:
            raise ValidationError(
                'Tell artists what you are looking for, or untick '
                '"Looking for Talent".'
            )


class ArtistForm(_ListingForm):
    seeking_venue = BooleanField('seeking_venue')

    def validate_seeking_description(self, field):
        """Mirrors the ck_artist_seeking_description CHECK constraint."""
        if self.seeking_venue.data and not field.data:
            raise ValidationError(
                'Tell venues what you are looking for, or untick '
                '"Looking for Venues".'
            )


class ShowForm(FlaskForm):
    """Booking form.

    The cross-record rules (does the artist exist? is the artist free?) are
    validated here rather than in the controller, so the controller only has to
    ask ``form.validate_on_submit()`` and render whatever messages came back.
    """

    artist_id = IntegerField(
        'artist_id',
        validators=[DataRequired(message='Artist ID is required.'),
                    NumberRange(min=1, message='Artist ID must be positive.')],
    )
    venue_id = IntegerField(
        'venue_id',
        validators=[DataRequired(message='Venue ID is required.'),
                    NumberRange(min=1, message='Venue ID must be positive.')],
    )
    start_time = DateTimeLocalField(
        'start_time',
        validators=[DataRequired(message='Start time is required.')],
        format=DATETIME_FORMATS,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filled in by the validators so the controller can reuse the rows it
        # has already paid a query for.
        self.artist = None
        self.venue = None

    def validate_artist_id(self, field):
        from models import Artist  # imported lazily: models imports nothing here

        self.artist = db_get(Artist, field.data)
        if self.artist is None:
            raise ValidationError('No artist with ID {}.'.format(field.data))

    def validate_venue_id(self, field):
        from models import Venue

        self.venue = db_get(Venue, field.data)
        if self.venue is None:
            raise ValidationError('No venue with ID {}.'.format(field.data))

    def validate_start_time(self, field):
        """Reject double bookings and times outside the artist's availability.

        Both rules also exist in the database (a unique index on
        ``(artist_id, start_time)``, and the availability check below); catching
        them here turns an IntegrityError into a sentence a user can act on.
        """
        from extensions import db
        from models import Show

        when = as_utc(field.data)
        field.data = when

        if self.artist is None:
            return  # artist_id already failed; no point piling on

        clash = db.session.scalars(
            db.select(Show).where(Show.artist_id == self.artist.id,
                                  Show.start_time == when)
        ).first()
        if clash is not None:
            raise ValidationError(
                '{} is already booked at {} UTC.'.format(
                    self.artist.name, utc_label(when))
            )

        if not self.artist.is_available_at(when):
            listed = '; '.join(
                '{} to {}'.format(utc_label(window.start_time),
                                  utc_label(window.end_time))
                for window in self.artist.availabilities
            )
            raise ValidationError(
                '{} is not available then. Bookable windows (UTC): {}'.format(
                    self.artist.name, listed or 'none published')
            )


class AvailabilityForm(FlaskForm):
    """A window during which an artist accepts bookings."""

    start_time = DateTimeLocalField(
        'start_time',
        validators=[DataRequired(message='Start time is required.')],
        format=DATETIME_FORMATS,
    )
    end_time = DateTimeLocalField(
        'end_time',
        validators=[DataRequired(message='End time is required.')],
        format=DATETIME_FORMATS,
    )

    def __init__(self, *args, artist=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.artist = artist

    def validate_end_time(self, field):
        """Mirrors ck_availability_order, plus an overlap check."""
        if self.start_time.data and field.data <= self.start_time.data:
            raise ValidationError('The window must end after it starts.')

        if self.artist is None or self.start_time.data is None:
            return

        start, end = as_utc(self.start_time.data), as_utc(field.data)
        overlapping = [window for window in self.artist.availabilities
                       if window.overlaps(start, end)]
        if overlapping:
            raise ValidationError(
                'That window overlaps one you already published '
                '({} to {} UTC).'.format(
                    utc_label(overlapping[0].start_time),
                    utc_label(overlapping[0].end_time))
            )


class SongForm(FlaskForm):
    """One track. Used only as a sub-form of AlbumForm."""

    class Meta:
        # Sub-forms must not emit their own CSRF token; the parent carries one.
        csrf = False

    title = StringField('title', filters=[strip],
                        validators=[Optional(), Length(max=200)])
    track_number = IntegerField('track_number',
                                validators=[Optional(), NumberRange(min=1)])
    duration_seconds = IntegerField(
        'duration_seconds',
        validators=[Optional(), NumberRange(min=1, max=7200)],
    )


class AlbumForm(FlaskForm):
    """An album plus a handful of tracks, submitted together."""

    name = StringField(
        'name', filters=[strip],
        validators=[DataRequired(message='Album name is required.'),
                    Length(max=120)],
    )
    release_year = IntegerField(
        'release_year',
        validators=[Optional(),
                    NumberRange(min=1877, max=2100,
                                message='Release year must be between 1877 '
                                        'and 2100.')],
    )
    image_link = StringField('image_link', filters=[strip],
                             validators=[Optional(), URL(), Length(max=500)])
    songs = FieldList(FormField(SongForm), min_entries=5, max_entries=25)

    def validate_songs(self, field):
        """Mirrors uq_song_album_title and uq_song_album_track."""
        titles = [entry.title.data for entry in field.entries
                  if entry.title.data]
        if len(titles) != len(set(titles)):
            raise ValidationError('Two tracks on this album share a title.')

        numbers = [entry.track_number.data for entry in field.entries
                   if entry.title.data and entry.track_number.data]
        if len(numbers) != len(set(numbers)):
            raise ValidationError('Two tracks share a track number.')
