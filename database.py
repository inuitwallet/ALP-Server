import sqlite3
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
    log.info('create the users table')
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user TEXT, "
              "address TEXT, exchange TEXT, unit TEXT)")
    log.info('create the orders table')
    c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user TEXT, "
              "rank TEXT, order_id TEXT, order_amount NUMBER, side TEXT, "
              "order_price NUMBER, server_price NUMBER, exchange TEXT, unit TEXT, "
              "deviation NUMBER, credited INTEGER)")
    log.info('create the credits table')
    c.execute("CREATE TABLE IF NOT EXISTS credits (id INTEGER PRIMARY KEY, time NUMBER, "
              "user TEXT, exchange TEXT, unit TEXT, rank TEXT, side TEXT, "
              "order_id NUMBER, provided NUMBER, total NUMBER, percentage NUMBER, "
              "reward NUMBER, paid INTEGER)")
    log.info('create the stats table')
    c.execute("CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, time NUMBER, "
              "meta TEXT, totals TEXT, rewards TEXT)")
    log.info('create the info table')
    c.execute("CREATE TABLE IF NOT EXISTS info (key Text, value Text)")
    c.execute("INSERT INTO info VALUES (?, ?)", ('last_credit_time', 0))
    c.execute("INSERT INTO info VALUES (?, ?)", ('next_payout_time', 0))
    conn.commit()
    conn.close()
    return


def get_db(app):
    """
    Determine which database to use based on Environment Variables and return a
    database cursor object
    :return:
    """
    if os.getenv('DATABASE', '') == 'POSTGRES':
        conn = psycopg2.connect('dbname={} user={} password={} host={}'.format(
            app.config['db.name'], app.config['db.user'], app.config['db.pass'],
            app.config['db.host']))
    else:
        conn = sqlite3.connect('pool.db')
    return conn

