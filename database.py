import sqlite3

__author__ = 'sammoth'


def build():
    """
    Build the necessary tables in the database
    use the 'IF NOT EXISTS' clause to allow for repeated running without barfing
    :return:
    """
    conn = sqlite3.connect('pool.db')
    c = conn.cursor()
    # create the users table
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, user TEXT, "
              "address TEXT, exchange TEXT, unit TEXT)")
    # create the orders table
    c.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user TEXT, "
              "tier TEXT, order_id TEXT, order_amount NUMBER, order_type TEXT, exchange "
              "TEXT, unit TEXT)")
    # create the credits table
    c.execute("CREATE TABLE IF NOT EXISTS credits (id INTEGER PRIMARY KEY, time NUMBER, "
              "user TEXT, exchange TEXT, unit TEXT, tier TEXT, side TEXT, provided "
              "NUMBER, total NUMBER, percentage NUMBER, reward NUMBER, paid INTEGER)")
    conn.commit()
    conn.close()
    return
