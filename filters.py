"""Jinja filters."""

import babel.dates
import dateutil.parser


def format_datetime(value, format='medium'):
    """Render a timestamp for the templates.

    Accepts either an ISO-8601 string (what the controllers pass, matching the
    shape of the original mock payloads) or a `datetime` (handy in templates
    that work with model objects directly), so neither caller has to convert.

    Rendering is pinned to UTC. Babel would otherwise convert an aware datetime
    to the *server's* local zone, so a show entered as 20:00 would come back as
    16:00 on an Eastern machine -- the app stores, validates and displays one
    clock, and says so on the booking form.
    """
    if value is None:
        return ''

    date = dateutil.parser.parse(value) if isinstance(value, str) else value

    if format == 'full':
        format = "EEEE MMMM, d, y 'at' h:mma"
    elif format == 'medium':
        format = "EE MM, dd, y h:mma"
    return babel.dates.format_datetime(date, format,
                                       tzinfo=babel.dates.UTC, locale='en')


def register_filters(app):
    app.jinja_env.filters['datetime'] = format_datetime
