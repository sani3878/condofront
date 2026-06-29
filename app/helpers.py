import psycopg2
import psycopg2.extras
from flask import current_app, g
from urllib.parse import unquote  # ← add this

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(
            host=current_app.config['DB_HOST'],
            dbname=current_app.config['DB_NAME'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASS'],
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_one(sql, params=None):
    """Execute SQL and return one row as dict, or None."""
    cur = get_db().cursor()
    cur.execute(sql, params or [])
    return cur.fetchone()

def query_all(sql, params=None):
    """Execute SQL and return all rows as list of dicts."""
    cur = get_db().cursor()
    cur.execute(sql, params or [])
    return cur.fetchall()

def execute(sql, params=None):
    """Execute INSERT/UPDATE/DELETE, return lastrowid."""
    db  = get_db()
    cur = db.cursor()
    cur.execute(sql, params or [])
    db.commit()
    return cur.fetchone() if cur.description else None
