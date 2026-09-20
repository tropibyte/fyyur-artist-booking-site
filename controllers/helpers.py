"""Small shared pieces of the HTTP layer: flashing, committing, logging."""

from flask import current_app, flash
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db

# A constraint violation reaching this layer means a race, a direct SQL insert,
# or a rule the forms do not mirror.  Translate the ones we can name; anything
# else falls back to the caller's generic message.
CONSTRAINT_MESSAGES = {
    'uq_venue_name_address':
        'A venue with that name is already listed at that address.',
    'uq_artist_name_city':
        'An artist with that name is already listed in that city.',
    'uq_show_artist_start_time':
        'That artist is already booked at that date and time.',
    'uq_availability_window':
        'That availability window is already published.',
    'uq_album_artist_name':
        'That artist already has an album with that name.',
    'uq_song_album_title': 'Two tracks on that album share a title.',
    'uq_song_album_track': 'Two tracks on that album share a track number.',
    'ck_venue_state': 'That is not a valid US state code.',
    'ck_artist_state': 'That is not a valid US state code.',
    'ck_genre_name_allowed': 'That is not a genre Fyyur recognises.',
    'ck_availability_order': 'An availability window must end after it starts.',
}


def describe_integrity_error(error, fallback):
    """Turn a Postgres constraint violation into a sentence, when we know it."""
    diagnostics = getattr(getattr(error, 'orig', None), 'diag', None)
    constraint = getattr(diagnostics, 'constraint_name', None)
    return CONSTRAINT_MESSAGES.get(constraint, fallback)


def commit(success=None, failure='An error occurred. Please try again.'):
    """Commit the session, flashing a readable message either way.

    Returns True on success.  Every failure path rolls back, so the session is
    always usable afterwards -- a half-failed transaction left open is what
    turns one bad request into a stream of 500s.
    """
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        current_app.logger.warning('Integrity error: %s', error.orig)
        flash(describe_integrity_error(error, failure), 'error')
        return False
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Database error')
        flash(failure, 'error')
        return False

    if success:
        flash(success)
    return True


def flash_validation_summary(form, subject=None):
    """Tell the user the submission was rejected; the form shows the detail.

    Each field renders its own errors inline (see `layouts/form_macros.html`),
    so repeating all of them up here would say the same thing twice.
    """
    count = sum(len(errors) for errors in form.errors.values())
    flash('{} could not be saved: please correct the {} highlighted '
          '{} below.'.format(subject or 'This form', count,
                             'field' if count == 1 else 'fields'), 'error')
