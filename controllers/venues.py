"""Venue endpoints: list, search, detail, create, edit, delete."""

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
from forms import VenueForm
from models import Venue

venues_bp = Blueprint('venues', __name__)


#  Read
#  ----------------------------------------------------------------

@venues_bp.route('/venues')
def list_venues():
    """Venues grouped by city and state.

    The grouping and the per-venue upcoming-show counts come from one query;
    see `Venue.grouped_by_area`.
    """
    return render_template('pages/venues.html', areas=Venue.grouped_by_area())


@venues_bp.route('/venues/search', methods=['POST'])
def search_venues():
    """Case-insensitive partial search, or a "City, ST" place search.

    "Hop" finds "The Musical Hop"; "music" finds "The Musical Hop" and
    "Park Square Live Music & Coffee"; "San Francisco, CA" finds every venue
    in that city.
    """
    search_term = request.form.get('search_term', '')
    return render_template('pages/search_venues.html',
                           results=Venue.search(search_term),
                           search_term=search_term)


@venues_bp.route('/venues/<int:venue_id>')
def show_venue(venue_id):
    """One venue, with its past and upcoming shows."""
    venue = db.get_or_404(Venue, venue_id)
    return render_template('pages/show_venue.html',
                           venue=venue.to_detail_dict())


#  Create
#  ----------------------------------------------------------------

@venues_bp.route('/venues/create', methods=['GET'])
def create_venue_form():
    return render_template('forms/new_venue.html', form=VenueForm())


@venues_bp.route('/venues/create', methods=['POST'])
def create_venue_submission():
    """Insert a new Venue.

    SQL equivalent: INSERT INTO "Venue" (name, city, state, address, ...)
                    VALUES (...) RETURNING id;
                    plus one INSERT per selected genre into "VenueGenre".
    """
    form = VenueForm()
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Venue')
        return render_template('forms/new_venue.html', form=form), 400

    venue = Venue().apply_form(form)
    db.session.add(venue)

    if not commit(success='Venue ' + venue.name + ' was successfully listed!',
                  failure='An error occurred. Venue ' + (form.name.data or '')
                          + ' could not be listed.'):
        return render_template('forms/new_venue.html', form=form), 400

    return redirect(url_for('main.index'))


#  Update
#  ----------------------------------------------------------------

@venues_bp.route('/venues/<int:venue_id>/edit', methods=['GET'])
def edit_venue(venue_id):
    venue = db.get_or_404(Venue, venue_id)
    form = VenueForm(obj=venue)
    # `obj=` cannot populate a many-to-many; hand the select its values.
    form.genres.data = [genre.name for genre in venue.genres]
    return render_template('forms/edit_venue.html', form=form, venue=venue)


@venues_bp.route('/venues/<int:venue_id>/edit', methods=['POST'])
def edit_venue_submission(venue_id):
    """UPDATE "Venue" SET ... WHERE id = :venue_id"""
    venue = db.get_or_404(Venue, venue_id)
    form = VenueForm()
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Venue')
        return render_template('forms/edit_venue.html', form=form,
                               venue=venue), 400

    venue.apply_form(form)
    if not commit(success='Venue ' + venue.name + ' was successfully updated!',
                  failure='An error occurred. Venue could not be updated.'):
        return render_template('forms/edit_venue.html', form=form,
                               venue=venue), 400

    return redirect(url_for('venues.show_venue', venue_id=venue_id))


#  Delete
#  ----------------------------------------------------------------

@venues_bp.route('/venues/<int:venue_id>', methods=['DELETE'])
def delete_venue(venue_id):
    """Delete a venue and, by cascade, its shows.

    Answers the fetch() call made by the delete button on the venue page; the
    browser is told where to go next because fetch() will not follow a redirect
    on the user's behalf.
    """
    venue = db.session.get(Venue, venue_id)
    if venue is None:
        abort(404)

    name = venue.name
    db.session.delete(venue)
    if not commit(success='Venue ' + name + ' was successfully deleted.',
                  failure='An error occurred. Venue ' + name
                          + ' could not be deleted.'):
        return jsonify({'success': False}), 500

    return jsonify({'success': True, 'redirect': url_for('main.index')})


@venues_bp.route('/venues/<int:venue_id>/delete', methods=['POST'])
def delete_venue_submission(venue_id):
    """Same deletion, for clients without JavaScript."""
    venue = db.get_or_404(Venue, venue_id)
    name = venue.name
    db.session.delete(venue)
    commit(success='Venue ' + name + ' was successfully deleted.',
           failure='An error occurred. Venue ' + name
                   + ' could not be deleted.')
    return redirect(url_for('venues.list_venues'))
