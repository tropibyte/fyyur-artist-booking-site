"""Artist endpoints: list, search, detail, create, edit, delete -- plus the
two stand-out features that hang off an artist, availability windows and the
discography."""

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from controllers.helpers import commit, flash_validation_summary
from extensions import db
from forms import AlbumForm, ArtistForm, AvailabilityForm, as_utc
from models import Album, Artist, Availability, Song

artists_bp = Blueprint('artists', __name__)


#  Read
#  ----------------------------------------------------------------

@artists_bp.route('/artists')
def list_artists():
    return render_template('pages/artists.html', artists=Artist.listing())


@artists_bp.route('/artists/search', methods=['POST'])
def search_artists():
    """Case-insensitive partial search, or a "City, ST" place search.

    "A" finds "Guns N Petals", "Matt Quevedo" and "The Wild Sax Band";
    "band" finds "The Wild Sax Band"; "New York, NY" finds every artist there.
    """
    search_term = request.form.get('search_term', '')
    return render_template('pages/search_artists.html',
                           results=Artist.search(search_term),
                           search_term=search_term)


@artists_bp.route('/artists/<int:artist_id>')
def show_artist(artist_id):
    artist = db.get_or_404(Artist, artist_id)
    return render_template('pages/show_artist.html',
                           artist=artist.to_detail_dict())


#  Create
#  ----------------------------------------------------------------

@artists_bp.route('/artists/create', methods=['GET'])
def create_artist_form():
    return render_template('forms/new_artist.html', form=ArtistForm())


@artists_bp.route('/artists/create', methods=['POST'])
def create_artist_submission():
    """INSERT INTO "Artist" (...) VALUES (...), plus rows in "ArtistGenre"."""
    form = ArtistForm()
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Artist')
        return render_template('forms/new_artist.html', form=form), 400

    artist = Artist().apply_form(form)
    db.session.add(artist)

    if not commit(success='Artist ' + artist.name + ' was successfully listed!',
                  failure='An error occurred. Artist ' + (form.name.data or '')
                          + ' could not be listed.'):
        return render_template('forms/new_artist.html', form=form), 400

    return redirect(url_for('main.index'))


#  Update
#  ----------------------------------------------------------------

@artists_bp.route('/artists/<int:artist_id>/edit', methods=['GET'])
def edit_artist(artist_id):
    artist = db.get_or_404(Artist, artist_id)
    form = ArtistForm(obj=artist)
    form.genres.data = [genre.name for genre in artist.genres]
    return render_template('forms/edit_artist.html', form=form, artist=artist)


@artists_bp.route('/artists/<int:artist_id>/edit', methods=['POST'])
def edit_artist_submission(artist_id):
    """UPDATE "Artist" SET ... WHERE id = :artist_id"""
    artist = db.get_or_404(Artist, artist_id)
    form = ArtistForm()
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Artist')
        return render_template('forms/edit_artist.html', form=form,
                               artist=artist), 400

    artist.apply_form(form)
    if not commit(success='Artist ' + artist.name + ' was successfully updated!',
                  failure='An error occurred. Artist could not be updated.'):
        return render_template('forms/edit_artist.html', form=form,
                               artist=artist), 400

    return redirect(url_for('artists.show_artist', artist_id=artist_id))


#  Delete
#  ----------------------------------------------------------------

@artists_bp.route('/artists/<int:artist_id>', methods=['DELETE'])
def delete_artist(artist_id):
    artist = db.session.get(Artist, artist_id)
    if artist is None:
        abort(404)

    name = artist.name
    db.session.delete(artist)
    if not commit(success='Artist ' + name + ' was successfully deleted.',
                  failure='An error occurred. Artist ' + name
                          + ' could not be deleted.'):
        return jsonify({'success': False}), 500

    return jsonify({'success': True, 'redirect': url_for('main.index')})


@artists_bp.route('/artists/<int:artist_id>/delete', methods=['POST'])
def delete_artist_submission(artist_id):
    artist = db.get_or_404(Artist, artist_id)
    name = artist.name
    db.session.delete(artist)
    commit(success='Artist ' + name + ' was successfully deleted.',
           failure='An error occurred. Artist ' + name
                   + ' could not be deleted.')
    return redirect(url_for('artists.list_artists'))


#  Availability  (stand-out: artists publish the times they can be booked)
#  ----------------------------------------------------------------

@artists_bp.route('/artists/<int:artist_id>/availability', methods=['GET'])
def availability_form(artist_id):
    artist = db.get_or_404(Artist, artist_id)
    return render_template('forms/new_availability.html',
                           form=AvailabilityForm(artist=artist),
                           artist=artist)


@artists_bp.route('/artists/<int:artist_id>/availability', methods=['POST'])
def create_availability(artist_id):
    """Publish a bookable window. `ShowForm` enforces it at booking time."""
    artist = db.get_or_404(Artist, artist_id)
    form = AvailabilityForm(artist=artist)
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Availability window')
        return render_template('forms/new_availability.html', form=form,
                               artist=artist), 400

    db.session.add(Availability(
        artist_id=artist.id,
        start_time=as_utc(form.start_time.data),
        end_time=as_utc(form.end_time.data),
    ))
    commit(success='Availability for ' + artist.name + ' was added.',
           failure='An error occurred. The window could not be added.')
    return redirect(url_for('artists.availability_form', artist_id=artist.id))


@artists_bp.route('/artists/<int:artist_id>/availability/<int:availability_id>'
                  '/delete', methods=['POST'])
def delete_availability(artist_id, availability_id):
    window = db.get_or_404(Availability, availability_id)
    if window.artist_id != artist_id:
        abort(404)

    db.session.delete(window)
    commit(success='Availability window removed.',
           failure='An error occurred. The window could not be removed.')
    return redirect(url_for('artists.availability_form', artist_id=artist_id))


#  Discography  (stand-out: albums and songs on the artist page)
#  ----------------------------------------------------------------

@artists_bp.route('/artists/<int:artist_id>/albums/create', methods=['GET'])
def create_album_form(artist_id):
    artist = db.get_or_404(Artist, artist_id)
    return render_template('forms/new_album.html', form=AlbumForm(),
                           artist=artist)


@artists_bp.route('/artists/<int:artist_id>/albums/create', methods=['POST'])
def create_album_submission(artist_id):
    """Insert an album and its tracks in one transaction.

    The songs are added to `album.songs` rather than inserted separately, so
    SQLAlchemy fills in the foreign key after the album's id exists -- and if
    any track violates a constraint, the album insert rolls back with it.
    """
    artist = db.get_or_404(Artist, artist_id)
    form = AlbumForm()
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Album')
        return render_template('forms/new_album.html', form=form,
                               artist=artist), 400

    album = Album(artist_id=artist.id, name=form.name.data,
                  release_year=form.release_year.data,
                  image_link=form.image_link.data)

    track_number = 0
    for entry in form.songs.entries:
        if not entry.title.data:
            continue  # blank rows in the fixed-size track list are ignored
        track_number += 1
        album.songs.append(Song(
            title=entry.title.data,
            track_number=entry.track_number.data or track_number,
            duration_seconds=entry.duration_seconds.data,
        ))

    db.session.add(album)
    if not commit(success='Album ' + album.name + ' was added to '
                          + artist.name + '.',
                  failure='An error occurred. The album could not be added.'):
        return render_template('forms/new_album.html', form=form,
                               artist=artist), 400

    return redirect(url_for('artists.show_artist', artist_id=artist.id))
