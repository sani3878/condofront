import os
import psycopg2
import psycopg2.extras
from flask import current_app, g


def get_db():
    if 'db' not in g:
        # Railway provides DATABASE_URL directly
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            g.db = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            g.db = psycopg2.connect(
                host=current_app.config['DB_HOST'],
                port=current_app.config.get('DB_PORT', 5432),
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
    cur = get_db().cursor()
    cur.execute(sql, params or [])
    return cur.fetchone()


def query_all(sql, params=None):
    cur = get_db().cursor()
    cur.execute(sql, params or [])
    return cur.fetchall()


def execute(sql, params=None):
    db = get_db()
    cur = db.cursor()
    cur.execute(sql, params or [])
    db.commit()
    return cur.fetchone() if cur.description else None
