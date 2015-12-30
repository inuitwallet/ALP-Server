import sqlite3
import urlparse

import psycopg2
import os

__author__ = 'sammoth'


def build(app, log):
    """
    Build the necessary tables in the database
    use the 'IF NOT EXISTS' clause to allow for repeated running without barfing
    :return:
    """
    conn = get_db(app)
    c = conn.cursor()
    log.info('create the database')
    c.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL, key TEXT, address "
              "TEXT, exchange TEXT, unit TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS orders (id SERIAL, key TEXT, rank TEXT, "
              "order_id TEXT, order_amount FLOAT8, side TEXT, order_price FLOAT8, "
              "server_price FLOAT8, exchange TEXT, unit TEXT, deviation FLOAT8, "
              "credited INT2)")
    c.execute("CREATE TABLE IF NOT EXISTS credits (id SERIAL, time FLOAT8, "
              "key TEXT, exchange TEXT, unit TEXT, rank TEXT, side TEXT, "
              "order_id FLOAT8, provided FLOAT8, total FLOAT8, percentage FLOAT8, "
              "reward FLOAT8, paid INT2)")
    c.execute("CREATE TABLE IF NOT EXISTS stats (id SERIAL, time FLOAT8, meta TEXT, "
              "totals TEXT, rewards TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS info (key TEXT, value TEXT)")
    c.execute("SELECT value FROM info WHERE key = %s", ('last_credit_time', ))
    if c.fetchone() is None:
        c.execute("INSERT INTO info VALUES (%s, %s)", ('last_credit_time', 0))
    c.execute("SELECT value FROM info WHERE key = %s", ('next_payout_time', ))
    if c.fetchone() is None:
        c.execute("INSERT INTO info VALUES (%s, %s)", ('next_payout_time', 0))
    conn.commit()
    conn.close()
    return


def get_db(app):
    """
    Determine which database to use based on Environment Variables and return a
    database cursor object
    :return:
    """
    if os.getenv("DATABASE_URL", None) is not None:
        urlparse.uses_netloc.append("postgres")
        url = urlparse.urlparse(os.environ["DATABASE_URL"])
        conn = psycopg2.connect(database=url.path[1:],
                                user=url.username,
                                password=url.password,
                                host=url.hostname,
                                port=url.port)
    else:
        conn = psycopg2.connect(database=app.config['db.name'],
                                user=app.config['db.user'],
                                password=app.config['db.pass'],
                                host=app.config['db.host'],
                                port=app.config['db.port'])
    return conn
