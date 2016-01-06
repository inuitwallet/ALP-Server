import logging
import random
import sys
import unittest

import bottle

sys.path.append('../')
from src import credit, database, config


class TestCredits(unittest.TestCase):

    def setUp(self):
        """
        Set up the database with some orders ready for a credit
        :return:
        """
        # Build the tests Logger
        self.log = logging.Logger('Tests')
        stream = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(message)s')
        stream.setFormatter(formatter)
        self.log.addHandler(stream)
        self.log.debug('TestCredits testcase')
        self.log.debug('running setUp')
        # set us up a bottle application with correct config
        self.app = bottle.Bottle()
        self.app.config.load_config('config/pool_config')
        config.load(self.app, 'config/exchange_config')
        # build the database if it doesn't exist
        database.build(self.app, self.log)
        # clear any existing orders in the database
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("DELETE FROM orders")
        c.execute("DELETE FROM credits")
        conn.commit()
        # create test data
        self.test_data = {
            'rank_1': {
                'TEST_USER_1': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)},
                'TEST_USER_2': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)},
                'TEST_USER_3': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)},
                'TEST_USER_4': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)}},
            'rank_2': {
                'TEST_USER_1': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)},
                'TEST_USER_2': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)},
                'TEST_USER_3': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)},
                'TEST_USER_4': {
                    'bid': random.randint(0, 1000),
                    'ask': random.randint(0, 1000)}}}
        # add some orders to the database for test_data
        for rank in self.test_data:
            for user in self.test_data[rank]:
                for side in self.test_data[rank][user]:
                    c.execute("INSERT INTO orders (key,rank,order_id,order_amount,side,"
                              "exchange,unit,credited) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                              (user, rank, random.randint(0, 250),
                               self.test_data[rank][user][side], side, 'test_exchange',
                               'btc', 0))
        conn.commit()
        conn.close()
        self.log.debug('ending setUp')

    def test_get_total_liquidity(self):
        """
        Test the get_total_liquidity function
        :return:
        """
        self.log.debug('running test_get_total_liquidity')
        # get the orders from the database
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("SELECT * FROM orders")
        orders = c.fetchall()

        # get the data for rank_1 as calculated by the test function
        total = credit.get_total_liquidity(self.app, orders)
        # calculate the total from our test data
        # (test data is always for one exchange and currency)
        real_total = {'rank_1': {'bid': 0.00, 'ask': 0.00},
                      'rank_2': {'bid': 0.00, 'ask': 0.00}}
        for user in self.test_data['rank_1']:
            real_total['rank_1']['bid'] += self.test_data['rank_1'][user]['bid']
            real_total['rank_1']['ask'] += self.test_data['rank_1'][user]['ask']
        for user in self.test_data['rank_2']:
            real_total['rank_2']['bid'] += self.test_data['rank_2'][user]['bid']
            real_total['rank_2']['ask'] += self.test_data['rank_2'][user]['ask']
        self.assertEqual(total['rank_1']['test_exchange']['btc']['bid'],
                         real_total['rank_1']['bid'])
        self.assertEqual(total['rank_1']['test_exchange']['btc']['ask'],
                         real_total['rank_1']['ask'])
        self.assertEqual(total['rank_2']['test_exchange']['btc']['bid'],
                         real_total['rank_2']['bid'])
        self.assertEqual(total['rank_2']['test_exchange']['btc']['ask'],
                         real_total['rank_2']['ask'])
        self.log.debug('ending test_get_total_liquidity')

    def test_crediting(self):
        """
        Test the credit function
        :return:
        """
        self.log.debug('running test_crediting')
        # calculate the correct values
        total = {
            'rank_1': {'bid': 0.00, 'ask': 0.00},
            'rank_2': {'bid': 0.00, 'ask': 0.00}}
        for rank in self.test_data:
            for user in self.test_data[rank]:
                for side in self.test_data[rank][user]:
                    total[rank][side] += self.test_data[rank][user][side]
        # Run the credit on the inserted data
        credit.credit(self.app, None, self.log, False)
        # get the credit details from the database
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("SELECT * FROM credits")
        credit_data = c.fetchall()
        # self.log.debug(credit_data)
        # check the credits are correct
        for cred in credit_data:
            # check the total liquidity is correct
            this_total = total[cred[5]][cred[6]]
            self.assertEqual(cred[9], this_total)
            # check the amount provided is correct
            this_amount = self.test_data[cred[5]][cred[2]][cred[6]]
            self.assertEqual(cred[8], this_amount)
            # check the percentage is correct
            this_percentage = (this_amount / this_total) * 100
            self.assertAlmostEqual(cred[10], this_percentage)
            # check the reward is credited correctly
            this_reward = (this_percentage / 100) * self.app.config['{}.{}.'
                                                                    '{}.{}.reward'
                                                                    ''.format(
                                                                        'test_exchange',
                                                                        'btc',
                                                                        cred[6],
                                                                        cred[5])]
            # Asert almost equal to avoid rounding errors at 10 d.p.
            self.assertAlmostEqual(cred[11], this_reward, 15)
        self.log.debug('ending test_crediting')
