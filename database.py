import sqlite3

__author__ = 'sammoth'


def build(log):
    """
    Build the necessary tables in the database
    use the 'IF NOT EXISTS' clause to allow for repeated running without barfing
    :return:
    """
    conn = sqlite3.connect('pool.db')
    c = conn.cursor()
    log.info('create the users table')
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user TEXT, "
              "address TEXT, exchange TEXT, unit TEXT)")
    log.info('create the orders table')
    c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user TEXT, "
              "rank TEXT, order_id TEXT, order_amount NUMBER, side TEXT, exchange "
              "TEXT, unit TEXT, credited INTEGER)")
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
    conn.commit()
    conn.close()
    return
