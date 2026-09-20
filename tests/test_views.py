"""End-to-end tests of every endpoint, against real HTTP responses."""

from extensions import db
from models import Artist, Availability, Show, Venue

VENUE_FORM = {
    'name': 'The Gaslight',
    'city': 'Austin',
    'state': 'TX',
    'address': '9 Rainey Street',
    'phone': '512-555-0100',
    'genres': ['Blues', 'Rock n Roll'],
    'facebook_link': 'https://www.facebook.com/thegaslight',
    'image_link': 'https://example.com/gaslight.jpg',
    'website_link': 'https://thegaslight.example.com',
    'seeking_talent': 'y',
    'seeking_description': 'Thursdays are open.',
}

ARTIST_FORM = {
    'name': 'Delta Wave',
    'city': 'Austin',
    'state': 'TX',
    'phone': '512-555-0111',
    'genres': ['Blues'],
    'facebook_link': 'https://www.facebook.com/deltawave',
    'image_link': 'https://example.com/delta.jpg',
    'website_link': 'https://deltawave.example.com',
}


def _text(response):
    return response.get_data(as_text=True)


# -- read paths --------------------------------------------------------------#

def test_home_page_lists_recent_records(client):
    body = _text(client.get('/'))
    assert 'Recently listed artists' in body
    assert 'Recently listed venues' in body
    assert 'The Wild Sax Band' in body
    assert 'Park Square Live Music &amp; Coffee' in body


def test_venues_page_groups_by_area(client):
    body = _text(client.get('/venues'))
    assert 'San Francisco, CA' in body
    assert 'New York, NY' in body
    assert 'The Musical Hop' in body


def test_artists_page_lists_every_artist(client):
    body = _text(client.get('/artists'))
    for name in ('Guns N Petals', 'Matt Quevedo', 'The Wild Sax Band'):
        assert name in body


def test_shows_page_lists_every_show(client):
    body = _text(client.get('/shows'))
    assert body.count('playing at') == 5


def test_venue_detail_shows_past_and_upcoming(client):
    body = _text(client.get('/venues/3'))
    assert '3 Upcoming Shows' in body
    assert '1 Past Show' in body
    assert 'Matt Quevedo' in body


def test_artist_detail_shows_discography_and_availability(client):
    body = _text(client.get('/artists/4'))
    assert 'Petals &amp; Pistols' in body      # album
    assert 'Thorns on Sunset' in body          # track
    assert 'Availability' in body
    assert '1 Past Show' in body


def test_artist_with_no_windows_says_so(client):
    body = _text(client.get('/artists/5'))
    assert 'can be booked at any time' in body


def test_missing_records_404(client):
    assert client.get('/venues/9999').status_code == 404
    assert client.get('/artists/9999').status_code == 404


# -- search ------------------------------------------------------------------#

def test_venue_search_is_partial_and_case_insensitive(client):
    body = _text(client.post('/venues/search', data={'search_term': 'music'}))
    assert 'Number of search results for "music": 2' in body
    assert 'The Musical Hop' in body


def test_artist_search_matches_a_single_letter(client):
    body = _text(client.post('/artists/search', data={'search_term': 'A'}))
    assert 'Number of search results for "A": 3' in body


def test_search_by_city_and_state(client):
    body = _text(client.post('/venues/search',
                             data={'search_term': 'San Francisco, CA'}))
    assert 'Number of search results for "San Francisco, CA": 2' in body

    body = _text(client.post('/artists/search',
                             data={'search_term': 'New York, NY'}))
    assert 'Matt Quevedo' in body


# -- create venue ------------------------------------------------------------#

def test_create_venue(client):
    response = client.post('/venues/create', data=VENUE_FORM,
                           follow_redirects=True)
    assert response.status_code == 200
    assert 'The Gaslight was successfully listed!' in _text(response)

    venue = db.session.scalars(
        db.select(Venue).where(Venue.name == 'The Gaslight')).one()
    assert venue.city == 'Austin'
    assert sorted(genre.name for genre in venue.genres) == ['Blues',
                                                            'Rock n Roll']
    # ... and it is immediately findable.
    body = _text(client.post('/venues/search', data={'search_term': 'gaslight'}))
    assert 'The Gaslight' in body


def test_create_venue_rejects_an_invalid_state(client):
    payload = dict(VENUE_FORM, state='ZZ')
    response = client.post('/venues/create', data=payload)
    assert response.status_code == 400
    assert 'Not a valid choice' in _text(response)
    assert db.session.scalars(
        db.select(Venue).where(Venue.name == 'The Gaslight')).all() == []


def test_create_venue_rejects_missing_required_fields(client):
    for field in ('name', 'city', 'address', 'genres'):
        payload = dict(VENUE_FORM)
        payload.pop(field)
        response = client.post('/venues/create', data=payload)
        assert response.status_code == 400, field
    assert db.session.scalars(
        db.select(Venue).where(Venue.name == 'The Gaslight')).all() == []


def test_create_venue_rejects_a_bad_phone_and_url(client):
    response = client.post('/venues/create',
                           data=dict(VENUE_FORM, phone='call me'))
    assert response.status_code == 400
    assert 'Phone must look like' in _text(response)

    response = client.post('/venues/create',
                           data=dict(VENUE_FORM, website_link='not-a-url'))
    assert response.status_code == 400
    assert 'Website must be a valid URL' in _text(response)


def test_create_venue_rejects_a_duplicate(client):
    duplicate = dict(VENUE_FORM, name='The Musical Hop',
                     city='San Francisco', state='CA',
                     address='1015 Folsom Street')
    response = client.post('/venues/create', data=duplicate)
    assert response.status_code == 400
    assert 'already listed at that address' in _text(response)


def test_seeking_talent_requires_a_description(client):
    payload = dict(VENUE_FORM)
    payload['seeking_description'] = ''
    response = client.post('/venues/create', data=payload)
    assert response.status_code == 400
    assert 'untick' in _text(response)


# -- create artist -----------------------------------------------------------#

def test_create_artist(client):
    response = client.post('/artists/create', data=ARTIST_FORM,
                           follow_redirects=True)
    assert 'Delta Wave was successfully listed!' in _text(response)

    artist = db.session.scalars(
        db.select(Artist).where(Artist.name == 'Delta Wave')).one()
    assert artist.seeking_venue is False

    assert 'Delta Wave' in _text(client.get('/artists'))
    assert 'Delta Wave' in _text(
        client.post('/artists/search', data={'search_term': 'delta'}))


def test_create_artist_rejects_missing_fields(client):
    payload = dict(ARTIST_FORM)
    del payload['name']
    assert client.post('/artists/create', data=payload).status_code == 400


# -- edit --------------------------------------------------------------------#

def test_edit_venue_prefills_and_saves(client):
    body = _text(client.get('/venues/1/edit'))
    assert 'The Musical Hop' in body

    payload = dict(VENUE_FORM, name='The Musical Hop Renamed',
                   city='San Francisco', state='CA',
                   address='1015 Folsom Street')
    response = client.post('/venues/1/edit', data=payload,
                           follow_redirects=True)
    assert response.status_code == 200
    assert db.session.get(Venue, 1).name == 'The Musical Hop Renamed'


def test_edit_artist_saves_genres(client):
    payload = dict(ARTIST_FORM, name='Guns N Petals', city='San Francisco',
                   state='CA', genres=['Punk', 'Soul'])
    client.post('/artists/4/edit', data=payload, follow_redirects=True)
    assert sorted(g.name for g in db.session.get(Artist, 4).genres) == ['Punk',
                                                                        'Soul']


# -- create show -------------------------------------------------------------#

def test_create_show_appears_on_both_pages(client):
    """The rubric's click-through: an upcoming show on the artist page links to
    the venue page, and shows up there too."""
    response = client.post('/shows/create', data={
        'artist_id': 6, 'venue_id': 1, 'start_time': '2035-04-02T20:00',
    }, follow_redirects=True)
    assert 'Show was successfully listed!' in _text(response)

    artist_page = _text(client.get('/artists/6'))
    assert '/venues/1' in artist_page
    assert 'The Musical Hop' in artist_page

    venue_page = _text(client.get('/venues/1'))
    assert 'The Wild Sax Band' in venue_page
    assert '1 Upcoming Show' in venue_page


def test_create_show_rejects_unknown_ids(client):
    response = client.post('/shows/create', data={
        'artist_id': 999, 'venue_id': 1, 'start_time': '2035-04-02T20:00'})
    assert response.status_code == 400
    assert 'No artist with ID 999' in _text(response)

    response = client.post('/shows/create', data={
        'artist_id': 6, 'venue_id': 999, 'start_time': '2035-04-02T20:00'})
    assert response.status_code == 400
    assert 'No venue with ID 999' in _text(response)


def test_create_show_rejects_a_double_booking(client):
    response = client.post('/shows/create', data={
        'artist_id': 6, 'venue_id': 1, 'start_time': '2035-04-01T20:00'})
    assert response.status_code == 400
    assert 'already booked' in _text(response)


def test_create_show_respects_artist_availability(client):
    """Guns N Petals publishes January and February windows only."""
    rejected = client.post('/shows/create', data={
        'artist_id': 4, 'venue_id': 1, 'start_time': '2035-03-01T20:00'})
    assert rejected.status_code == 400
    assert 'is not available then' in _text(rejected)

    accepted = client.post('/shows/create', data={
        'artist_id': 4, 'venue_id': 1, 'start_time': '2035-01-05T20:00'},
        follow_redirects=True)
    assert 'Show was successfully listed!' in _text(accepted)


def test_availability_message_is_labelled_in_utc(client):
    """Postgres returns timestamptz in the session's zone; the message converts
    it back before claiming to be UTC."""
    body = _text(client.post('/shows/create', data={
        'artist_id': 4, 'venue_id': 1, 'start_time': '2035-03-01T20:00'}))
    assert '2035-01-05 18:00 to 2035-01-05 23:59' in body


def test_create_show_rejects_a_missing_start_time(client):
    response = client.post('/shows/create',
                           data={'artist_id': 4, 'venue_id': 1,
                                 'start_time': ''})
    assert response.status_code == 400
    assert 'Start time is required' in _text(response)


# -- availability ------------------------------------------------------------#

def test_publish_and_remove_an_availability_window(client):
    response = client.post('/artists/5/availability', data={
        'start_time': '2036-05-01T18:00', 'end_time': '2036-05-01T23:00',
    }, follow_redirects=True)
    assert 'was added' in _text(response)

    window = db.session.scalars(
        db.select(Availability).where(Availability.artist_id == 5)).one()

    # Having published a window, the artist is no longer bookable outside it.
    rejected = client.post('/shows/create', data={
        'artist_id': 5, 'venue_id': 1, 'start_time': '2036-06-01T20:00'})
    assert 'is not available then' in _text(rejected)

    response = client.post(
        '/artists/5/availability/{}/delete'.format(window.id),
        follow_redirects=True)
    assert 'window removed' in _text(response)
    assert db.session.get(Availability, window.id) is None


def test_overlapping_windows_are_rejected(client):
    client.post('/artists/5/availability',
                data={'start_time': '2036-05-01T18:00',
                      'end_time': '2036-05-01T23:00'})
    response = client.post('/artists/5/availability',
                           data={'start_time': '2036-05-01T20:00',
                                 'end_time': '2036-05-02T02:00'})
    assert response.status_code == 400
    assert 'overlaps' in _text(response)


def test_a_window_must_end_after_it_starts(client):
    response = client.post('/artists/5/availability',
                           data={'start_time': '2036-05-01T23:00',
                                 'end_time': '2036-05-01T18:00'})
    assert response.status_code == 400
    assert 'must end after it starts' in _text(response)


# -- albums ------------------------------------------------------------------#

def test_create_an_album_with_tracks(client):
    payload = {
        'name': 'Second Set',
        'release_year': '2026',
        'image_link': 'https://example.com/cover.jpg',
        'songs-0-title': 'Opener',
        'songs-0-track_number': '1',
        'songs-0-duration_seconds': '215',
        'songs-1-title': 'Closer',
        'songs-1-track_number': '2',
        'songs-1-duration_seconds': '330',
    }
    response = client.post('/artists/5/albums/create', data=payload,
                           follow_redirects=True)
    assert 'was added to Matt Quevedo' in _text(response)

    body = _text(client.get('/artists/5'))
    assert 'Second Set' in body
    assert 'Opener' in body
    assert '5:30' in body  # 330 seconds rendered as m:ss


def test_album_rejects_an_impossible_release_year(client):
    response = client.post('/artists/5/albums/create',
                           data={'name': 'Time Traveller',
                                 'release_year': '1500'})
    assert response.status_code == 400
    assert 'Release year must be between' in _text(response)


# -- delete ------------------------------------------------------------------#

def test_delete_venue_over_ajax(client):
    response = client.delete('/venues/2')
    assert response.status_code == 200
    assert response.get_json()['success'] is True
    assert db.session.get(Venue, 2) is None


def test_delete_venue_over_a_form_post(client):
    response = client.post('/venues/2/delete', follow_redirects=True)
    assert response.status_code == 200
    assert db.session.get(Venue, 2) is None


def test_delete_artist_removes_its_shows(client):
    assert db.session.scalars(
        db.select(Show).where(Show.artist_id == 6)).all()

    assert client.delete('/artists/6').status_code == 200
    assert db.session.get(Artist, 6) is None
    assert db.session.scalars(
        db.select(Show).where(Show.artist_id == 6)).all() == []


def test_delete_missing_record_is_404(client):
    assert client.delete('/venues/9999').status_code == 404


# -- empty database ----------------------------------------------------------#

def test_pages_render_with_no_data(empty_client):
    for path in ('/', '/venues', '/artists', '/shows'):
        assert empty_client.get(path).status_code == 200
