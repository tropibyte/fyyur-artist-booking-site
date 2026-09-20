"""Flask extension singletons.

They are created here, unbound, and attached to the application inside
`create_app()`.  Keeping them in their own module is what lets `models.py`
import `db` without importing the application, which would otherwise be a
circular import.
"""

from flask_migrate import Migrate
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
# Site-wide CSRF: every POST/DELETE needs a token, including the search
# boxes in the navbar and the fetch() call behind the delete buttons.
csrf = CSRFProtect()
migrate = Migrate()
moment = Moment()
