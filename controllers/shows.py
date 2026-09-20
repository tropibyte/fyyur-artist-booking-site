"""Show endpoints: list and create."""

from flask import Blueprint, redirect, render_template, url_for

from controllers.helpers import commit, flash_validation_summary
from extensions import db
from forms import ShowForm
from models import Artist, Show, Venue

shows_bp = Blueprint('shows', __name__)


@shows_bp.route('/shows')
def list_shows():
    """Every show, joined to its artist and venue in a single query."""
    return render_template('pages/shows.html', shows=Show.listing())


def _show_form_context(form):
    """The booking form plus the pickers that make the IDs discoverable."""
    return {'form': form,
            'artists': Artist.listing(),
            'venues': Venue.listing()}


@shows_bp.route('/shows/create')
def create_shows():
    # renders form. do not touch.
    form = ShowForm()
    return render_template('forms/new_show.html', **_show_form_context(form))


@shows_bp.route('/shows/create', methods=['POST'])
def create_show_submission():
    """INSERT INTO "Show" (artist_id, venue_id, start_time) VALUES (...)

    `ShowForm` has already checked that both IDs exist, that the artist is not
    double-booked, and that the time falls inside one of the artist's published
    availability windows.
    """
    form = ShowForm()
    if not form.validate_on_submit():
        flash_validation_summary(form, 'Show')
        return render_template('forms/new_show.html',
                               **_show_form_context(form)), 400

    show = Show(artist_id=form.artist_id.data,
                venue_id=form.venue_id.data,
                start_time=form.start_time.data)
    db.session.add(show)

    if not commit(success='Show was successfully listed!',
                  failure='An error occurred. Show could not be listed.'):
        return render_template('forms/new_show.html',
                               **_show_form_context(form)), 400

    return redirect(url_for('shows.list_shows'))
