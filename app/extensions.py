import psycopg2
import psycopg2.extras
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view        = 'auth.login'
login_manager.login_message     = 'Please login to access this page.'
login_manager.login_message_category = 'warning'

def get_db(app):
    """Get a new database connection."""
    return psycopg2.connect(
        app.config['DATABASE_URL'],
        cursor_factory=psycopg2.extras.RealDictCursor
    )
