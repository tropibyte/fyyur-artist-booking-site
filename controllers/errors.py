"""Application-wide error handling."""

from flask import current_app, render_template

from extensions import db


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        # A 500 usually means an exception escaped mid-transaction.  Roll back
        # so the next request starts from a clean session rather than
        # inheriting a failed one.
        db.session.rollback()
        current_app.logger.error('Server error: %s', error)
        return render_template('errors/500.html'), 500
