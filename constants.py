"""Canonical enumerations shared by the forms, the models and the seed data.

Defining them once keeps three things from drifting apart: the choices a user
sees in a form, the values the `AnyOf` validators accept, and the values the
database CHECK constraint allows.
"""

# The 50 states plus the District of Columbia, as USPS two-letter codes.
US_STATES = (
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'HI',
    'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN',
    'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH',
    'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA',
    'WV', 'WI', 'WY',
)

# `(value, label)` pairs for WTForms `SelectField.choices`.
STATE_CHOICES = [(state, state) for state in US_STATES]

# The genre vocabulary.  Rows in the `Genre` table are created from this list
# by `flask seed-genres`, so the table is a closed set rather than free text.
GENRES = (
    'Alternative',
    'Blues',
    'Classical',
    'Country',
    'Electronic',
    'Folk',
    'Funk',
    'Hip-Hop',
    'Heavy Metal',
    'Instrumental',
    'Jazz',
    'Musical Theatre',
    'Pop',
    'Punk',
    'R&B',
    'Reggae',
    'Rock n Roll',
    'Soul',
    'Swing',
    'Other',
)

GENRE_CHOICES = [(genre, genre) for genre in GENRES]

# Accepts 555-555-5555, 5555555555, (555) 555-5555 and +1 variants.
PHONE_REGEX = r'^\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$'
