"""HTTP layer.

One blueprint per resource, each in its own module:

    main     /                      home page, error handlers
    venues   /venues/...            list, search, detail, create, edit, delete
    artists  /artists/...           the same, plus availability and albums
    shows    /shows/...             list and create

URL paths are unchanged from the starter, so every link in the templates still
resolves; only the *endpoint names* gained a blueprint prefix
(``venues.list_venues`` rather than ``venues``).
"""

from controllers.artists import artists_bp
from controllers.errors import register_error_handlers
from controllers.main import main_bp
from controllers.shows import shows_bp
from controllers.venues import venues_bp


def register_blueprints(app):
    """Attach every blueprint and error handler to `app`."""
    app.register_blueprint(main_bp)
    app.register_blueprint(venues_bp)
    app.register_blueprint(artists_bp)
    app.register_blueprint(shows_bp)
    register_error_handlers(app)
