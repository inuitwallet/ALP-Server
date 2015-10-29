import unittest
import sqlite3
import credit_test


class TestCredits(unittest.TestCase):

    def setUp(self):
        """
        Set up the database with some orders ready for a credit
        :return:
        """
        # clear any existing orders in the database
        conn = sqlite3.connect('../pool.db')
        c = conn.cursor()
        c.execute("DELETE FROM orders")
        # Insert 100 bid and 100 ask orders for each tier
        for x in xrange(100):
            c.execute("INSERT INTO orders ('user','tier','order_id','order_amount',"
                      "'order_type','exchange','unit') VALUES (?,?,?,?,?,?,?)",
                      ('TEST_USER', 1, str(x), float(10), 'bid', 'TEST_EXCHANGE', 'btc'))
            c.execute("INSERT INTO orders ('user','tier','order_id','order_amount',"
                      "'order_type','exchange','unit') VALUES (?,?,?,?,?,?,?)",
                      ('TEST_USER', 1, str(x), float(10), 'ask', 'TEST_EXCHANGE', 'btc'))
            c.execute("INSERT INTO orders ('user','tier','order_id','order_amount',"
                      "'order_type','exchange','unit') VALUES (?,?,?,?,?,?,?)",
                      ('TEST_USER', 2, str(x), float(10), 'bid', 'TEST_EXCHANGE', 'btc'))
            c.execute("INSERT INTO orders ('user','tier','order_id','order_amount',"
                      "'order_type','exchange','unit') VALUES (?,?,?,?,?,?,?)",
                      ('TEST_USER', 2, str(x), float(10), 'ask', 'TEST_EXCHANGE', 'btc'))
        conn.commit()
        conn.close()

    def test_crediting(self):
        credit_test.c