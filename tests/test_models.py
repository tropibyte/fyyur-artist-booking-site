"""Model, schema-constraint and query-helper tests."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from models import (
    Album,
    Artist,
    Availability,
    Genre,
    Show,
    Song,
    Venue,
    parse_city_state,
    utcnow,
)


def db_count():
    from sqlalchemy import func as sa_func

    return sa_func.count()


def _venue(**overrides):
    data = {
        'name': 'Test Room',
        'city': 'Austin',
        'state': 'TX',
        'address': '100 Test Street',
    }
    data.update(overrides)
    return Venue(**data)


def _artist(**overrides):
    data = {'name': 'Test Act', 'city': 'Austin', 'state': 'TX'}
    data.update(overrides)
    return Artist(**data)


# -- relationships -----------------------------------------------------------#

def test_show_links_artist_and_venue(seeded):
    """Show is the association object of a many-to-many between the two."""
    show = seeded.session.scalars(seeded.select(Show)).first()
    assert show.artist is not None and show.venue is not None
    assert show in show.artist.shows
    assert show in show.venue.shows
    # ... and the read-only far side of the relationship resolves.
    assert show.venue in show.artist.venues


def test_genres_are_a_many_to_many(seeded):
    venue = seeded.session.get(Venue, 1)
    assert sorted(genre.name for genre in venue.genres) == [
        'Classical', 'Folk', 'Jazz', 'Reggae', 'Swing']
    jazz = seeded.session.scalars(
        seeded.select(Genre).where(Genre.name == 'Jazz')).one()
    assert venue in jazz.venues


def test_deleting_a_venue_cascades_to_its_shows(seeded):
    venue = seeded.session.get(Venue, 3)
    show_ids = [show.id for show in venue.shows]
    assert show_ids

    seeded.session.delete(venue)
    seeded.session.commit()

    remaining = seeded.session.scalars(
        seeded.select(Show).where(Show.id.in_(show_ids))).all()
    assert remaining == []


def test_deleting_an_artist_cascades_to_albums_and_songs(seeded):
    artist = seeded.session.get(Artist, 4)
    album_ids = [album.id for album in artist.albums]
    assert album_ids

    seeded.session.delete(artist)
    seeded.session.commit()

    assert seeded.session.scalars(
        seeded.select(Album).where(Album.artist_id == 4)).all() == []
    assert seeded.session.scalars(
        seeded.select(Song).where(Song.album_id.in_(album_ids))).all() == []


# -- constraints -------------------------------------------------------------#

def test_duplicate_venue_is_rejected(seeded):
    seeded.session.add(_venue(name='The Musical Hop', city='San Francisco',
                              state='CA', address='1015 Folsom Street'))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_duplicate_artist_in_same_city_is_rejected(seeded):
    seeded.session.add(_artist(name='Guns N Petals', city='San Francisco',
                               state='CA'))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_same_artist_name_in_another_city_is_allowed(seeded):
    seeded.session.add(_artist(name='Guns N Petals', city='Reno', state='NV'))
    seeded.session.commit()  # no exception


def test_invalid_state_is_rejected_by_the_database(seeded):
    seeded.session.add(_venue(state='ZZ'))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_blank_name_is_rejected_by_the_database(seeded):
    seeded.session.add(_venue(name='   '))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_seeking_talent_requires_a_description(seeded):
    seeded.session.add(_venue(seeking_talent=True, seeking_description=None))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_an_artist_cannot_be_booked_twice_at_the_same_moment(seeded):
    # Artist 5 publishes no availability windows, so this exercises the unique
    # index rather than trg_show_within_availability.
    when = datetime(2036, 1, 1, 20, 0, tzinfo=timezone.utc)
    seeded.session.add(Show(artist_id=5, venue_id=1, start_time=when))
    seeded.session.commit()

    seeded.session.add(Show(artist_id=5, venue_id=2, start_time=when))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_show_outside_availability_is_rejected_by_the_database(seeded):
    """The rule holds without ShowForm: this writes straight through the ORM.

    Artist 4 publishes windows in 2019, Jan 2035 and Feb 2035 only.
    """
    outside = datetime(2035, 3, 1, 20, 0, tzinfo=timezone.utc)
    seeded.session.add(Show(artist_id=4, venue_id=1, start_time=outside))
    with pytest.raises(IntegrityError) as caught:
        seeded.session.commit()
    # The trigger names itself, which is what lets controllers.helpers turn it
    # into a readable flash instead of a 500.
    assert (caught.value.orig.diag.constraint_name
            == 'ck_show_within_availability')


def test_show_inside_availability_is_accepted_by_the_database(seeded):
    inside = datetime(2035, 1, 5, 21, 0, tzinfo=timezone.utc)
    seeded.session.add(Show(artist_id=4, venue_id=1, start_time=inside))
    seeded.session.commit()  # no exception


def test_artist_without_windows_stays_bookable_in_the_database(seeded):
    """Matt Quevedo publishes nothing, so the trigger must not block him."""
    whenever = datetime(2041, 7, 4, 20, 0, tzinfo=timezone.utc)
    seeded.session.add(Show(artist_id=5, venue_id=1, start_time=whenever))
    seeded.session.commit()  # no exception


def test_moving_a_show_outside_availability_is_also_rejected(seeded):
    """The trigger fires on UPDATE OF start_time, not only on INSERT."""
    show = seeded.session.scalars(
        seeded.select(Show).where(Show.artist_id == 6)).first()
    show.start_time = datetime(2035, 9, 9, 20, 0, tzinfo=timezone.utc)
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_availability_must_end_after_it_starts(seeded):
    start = datetime(2036, 1, 1, 20, 0, tzinfo=timezone.utc)
    seeded.session.add(Availability(artist_id=4, start_time=start,
                                    end_time=start - timedelta(hours=1)))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


def test_two_tracks_cannot_share_a_number(seeded):
    album = seeded.session.scalars(seeded.select(Album)).first()
    album.songs.append(Song(title='A brand new song', track_number=1))
    with pytest.raises(IntegrityError):
        seeded.session.commit()


# -- query helpers -----------------------------------------------------------#

def test_genre_vocabulary_is_seeded_by_the_migration(db):
    """`flask db upgrade` alone leaves the table usable -- no seed required."""
    from constants import GENRES

    names = {genre.name for genre in db.session.scalars(db.select(Genre))}
    assert set(GENRES) <= names


def test_unknown_genre_is_rejected_rather_than_created(seeded):
    before = seeded.session.scalar(
        seeded.select(db_count()).select_from(Genre))
    with pytest.raises(ValueError, match='Polka'):
        Genre.resolve(['Jazz', 'Polka'])
    seeded.session.rollback()
    after = seeded.session.scalar(seeded.select(db_count()).select_from(Genre))
    assert before == after


def test_venues_are_grouped_by_city_and_state(seeded):
    areas = Venue.grouped_by_area()
    keyed = {(area['city'], area['state']): area for area in areas}

    assert ('San Francisco', 'CA') in keyed
    assert ('New York', 'NY') in keyed
    assert len(keyed[('San Francisco', 'CA')]['venues']) == 2
    # Park Square has three shows in 2035.
    park_square = next(v for v in keyed[('San Francisco', 'CA')]['venues']
                       if v['name'].startswith('Park Square'))
    assert park_square['num_upcoming_shows'] == 3


def test_venue_search_is_partial_and_case_insensitive(seeded):
    assert Venue.search('hop')['count'] == 1
    assert Venue.search('MUSIC')['count'] == 2
    assert Venue.search('nothing here')['count'] == 0


def test_artist_search_is_partial_and_case_insensitive(seeded):
    assert Artist.search('a')['count'] == 3
    assert Artist.search('band')['count'] == 1
    assert Artist.search('BAND')['count'] == 1


def test_search_by_city_and_state(seeded):
    assert Venue.search('San Francisco, CA')['count'] == 2
    assert Artist.search('New York, NY')['count'] == 1
    assert Artist.search('CA')['count'] == 2
    # A city in the wrong state matches nothing.
    assert Venue.search('San Francisco, NY')['count'] == 0


def test_parse_city_state():
    assert parse_city_state('San Francisco, CA') == ('San Francisco', 'CA')
    assert parse_city_state('  new york ,  ny ') == ('new york', 'NY')
    assert parse_city_state('CA') == (None, 'CA')
    assert parse_city_state('Jazz') == (None, None)
    assert parse_city_state('San Francisco, XX') == (None, None)
    assert parse_city_state('') == (None, None)


def test_past_and_upcoming_shows_are_separated(seeded):
    venue = seeded.session.get(Venue, 3)
    past, upcoming = venue.shows_by_period()
    assert [show['artist_name'] for show in past] == ['Matt Quevedo']
    assert len(upcoming) == 3
    assert all(show['artist_name'] == 'The Wild Sax Band' for show in upcoming)

    artist = seeded.session.get(Artist, 4)
    past, upcoming = artist.shows_by_period()
    assert [show['venue_name'] for show in past] == ['The Musical Hop']
    assert upcoming == []


def test_detail_dict_matches_the_mock_payload_shape(seeded):
    data = seeded.session.get(Venue, 1).to_detail_dict()
    assert set(data) == {
        'id', 'name', 'genres', 'address', 'city', 'state', 'phone', 'website',
        'facebook_link', 'seeking_talent', 'seeking_description', 'image_link',
        'past_shows', 'upcoming_shows', 'past_shows_count',
        'upcoming_shows_count',
    }
    assert data['past_shows_count'] == 1
    assert data['past_shows'][0]['artist_name'] == 'Guns N Petals'

    artist = seeded.session.get(Artist, 4).to_detail_dict()
    for key in ('id', 'name', 'genres', 'city', 'state', 'phone', 'website',
                'facebook_link', 'seeking_venue', 'seeking_description',
                'image_link', 'past_shows', 'upcoming_shows',
                'past_shows_count', 'upcoming_shows_count'):
        assert key in artist


def test_recent_listings_are_newest_first_and_capped(seeded):
    for index in range(12):
        seeded.session.add(_artist(name='Newcomer {}'.format(index),
                                   city='Austin', state='TX'))
    seeded.session.commit()

    recent = Artist.recent(limit=10)
    assert len(recent) == 10
    assert recent[0].name == 'Newcomer 11'


def test_artist_availability(seeded):
    guns = seeded.session.get(Artist, 4)
    inside = datetime(2035, 1, 5, 20, 0, tzinfo=timezone.utc)
    outside = datetime(2035, 3, 1, 20, 0, tzinfo=timezone.utc)
    assert guns.is_available_at(inside) is True
    assert guns.is_available_at(outside) is False

    # An artist with no published windows is bookable at any time.
    matt = seeded.session.get(Artist, 5)
    assert matt.availabilities == []
    assert matt.is_available_at(outside) is True


def test_show_listing_joins_both_parents(seeded):
    rows = Show.listing()
    assert len(rows) == 5
    assert set(rows[0]) == {'venue_id', 'venue_name', 'artist_id',
                            'artist_name', 'artist_image_link', 'start_time'}
    # Newest first.
    assert rows[0]['start_time'] > rows[-1]['start_time']


def test_utcnow_is_timezone_aware():
    assert utcnow().tzinfo is not None


# -- index usability ---------------------------------------------------------#
#
# The seeded catalogue is three rows, so the planner will always choose a
# sequential scan on cost.  Disabling seqscan for the statement asks the real
# question: *can* this index serve this predicate at all?  The previous
# lower(name) b-tree could not, and nothing caught it.

def test_name_search_can_use_the_trigram_index(seeded):
    seeded.session.execute(text('SET LOCAL enable_seqscan = off'))
    plan = seeded.session.execute(text(
        'EXPLAIN SELECT id FROM "Venue" WHERE name ILIKE :pattern'
    ), {'pattern': '%music%'}).scalars().all()
    assert any('ix_venue_name_trgm' in line for line in plan), plan


def test_city_state_search_can_use_the_state_city_index(seeded):
    seeded.session.execute(text('SET LOCAL enable_seqscan = off'))
    plan = seeded.session.execute(text(
        'EXPLAIN SELECT id FROM "Venue" '
        'WHERE state = :state AND lower(city) = :city'
    ), {'state': 'CA', 'city': 'san francisco'}).scalars().all()
    assert any('ix_venue_state_city_lower' in line for line in plan), plan
