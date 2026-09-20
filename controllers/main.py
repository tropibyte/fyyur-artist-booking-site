"""Home page."""

from flask import Blueprint, current_app, render_template

from models import Artist, Venue

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page, with the most recently listed artists and venues.

    Stand-out requirement: "Show Recent Listed Artists and Recently Listed
    Venues on the homepage, returning results for Artists and Venues sorting by
    newly created. Limit to the 10 most recently listed items."
    """
    limit = current_app.config.get('RECENT_LISTING_LIMIT', 10)
    return render_template(
        'pages/home.html',
        recent_artists=Artist.recent(limit),
        recent_venues=Venue.recent(limit),
    )
