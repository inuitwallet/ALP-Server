import logging
import os
import random
import unittest
import sqlite3
import bottle
import sys
sys.path.append('../')
import credit
import database
import load_config


class TestCredits(unittest.TestCase):

    def setUp(self):
        """
        Set up the database with some orders ready for a credit
        :return:
        """
        # Build the tests Logger
        self.log = logging.Logger('Tests')
        stream = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s',
                                      datefmt='%y-%m-%d %H:%M:%S')
        stream.setFormatter(formatter)
        self.log.addHandler(stream)
        self.log.debug('TestCredits testcase')
        self.log.debug('running setUp')
        # build the database if it doesn't exist
        database.build(self.log)
        # set us up a bottle application with correct config
        self.app = bottle.Bottle()
        self.app.config.load_config('../pool_config')
        load_config.load(self.app, 'exchange_config')
        # clear any existing orders in the database
        conn = sqlite3.connect('pool.db')
        c = conn.cursor()
        c.execute("DELETE FROM orders")
        c.execute("DELETE FROM credits")
        conn.commit()
        # create test data
        self.test_data = {'tier_1': {'TEST_USER_1': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)},
                                     'TEST_USER_2': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)},
                                     'TEST_USER_3': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)},
                                     'TEST_USER_4': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)}},
                          'tier_2': {'TEST_USER_1': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)},
                                     'TEST_USER_2': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)},
                                     'TEST_USER_3': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)},
                                     'TEST_USER_4': {'bid': random.randint(0, 1000),
                                                     'ask': random.randint(0, 1000)}}}
        # add some orders to the database for test_data
        for tier in self.test_data:
            for user in self.test_data[tier]:
                for side in self.test_data[tier][user]:
                    c.execute("INSERT INTO orders ('user','tier','order_id',"
                              "'order_amount','order_type','exchange','unit') "
                              "VALUES (?,?,?,?,?,?,?)",
                              (user, tier, random.randint(0, 250),
                               self.test_data[tier][user][side], side, 'exchange',
                               'currency'))
        conn.commit()
        conn.close()
        self.log.debug('ending setUp')

    def tearDown(self):
        """
        Remove database file
        :return:
        """
        self.log.debug('running tearDown')
        os.remove('pool.db')

    def test_get_total_liquidity(self):
        """
        Test the get_total_liquidity function
        :return:
        """
        self.log.debug('running test_get_total_liquidity')
        # get the orders from the database
        conn = sqlite3.connect('pool.db')
        c = conn.cursor()
        orders = c.execute("SELECT * FROM orders").fetchall()

        # get the data for tier_1 as calculated by the test function
        tier_1_total = credit.get_total_liquidity(self.app, orders, 'tier_1')
        # calculate the total from our test data
        # (test data is always for one exchange and currency)
        real_tier_1_total = {'bid': 0.00, 'ask': 0.00}
        for user in self.test_data['tier_1']:
            real_tier_1_total['bid'] += self.test_data['tier_1'][user]['bid']
            real_tier_1_total['ask'] += self.test_data['tier_1'][user]['ask']
        self.assertEqual(tier_1_total['exchange']['currency']['bid'],
                         real_tier_1_total['bid'])
        self.assertEqual(tier_1_total['exchange']['currency']['ask'],
                         real_tier_1_total['ask'])

        # same for tier 2
        tier_2_total = credit.get_total_liquidity(self.app, orders, 'tier_2')
        real_tier_2_total = {'bid': 0.00, 'ask': 0.00}
        for user in self.test_data['tier_2']:
            real_tier_2_total['bid'] += self.test_data['tier_2'][user]['bid']
            real_tier_2_total['ask'] += self.test_data['tier_2'][user]['ask']
        self.assertEqual(tier_2_total['exchange']['currency']['bid'],
                         real_tier_2_total['bid'])
        self.assertEqual(tier_2_total['exchange']['currency']['ask'],
                         real_tier_2_total['ask'])
        self.log.debug('ending test_get_total_liquidity')

    def test_crediting(self):
        """
        Test the credit function
        :return:
        """
        self.log.debug('running test_crediting')
        # calculate the correct values
        total = {'tier_1': {'bid': 0.00, 'ask': 0.00},
                 'tier_2': {'bid': 0.00, 'ask': 0.00}}
        for tier in self.test_data:
            for user in self.test_data[tier]:
                for side in self.test_data[tier][user]:
                    total[tier][side] += self.test_data[tier][user][side]
        # Run the credit on the inserted data
        credit.credit(self.app, None, self.log, False)
        # get the credit details from the database
        conn = sqlite3.connect('pool.db')
        c = conn.cursor()
        credit_data = c.execute("SELECT * FROM credits").fetchall()
        # self.log.debug(credit_data)
        # check the credits are correct
        for cred in credit_data:
            # check the total liquidity is correct
            this_total = total[cred[5]][cred[6]]
            self.assertEqual(cred[8], this_total)
            # check the amount provided is correct
            this_amount = self.test_data[cred[5]][cred[2]][cred[6]]
            self.assertEqual(cred[7], this_amount)
            # check the percentage is correct
            this_percentage = (this_amount / this_total) * 100
            self.assertEqual(cred[9], this_percentage)
            # check the reward is credited correctly
            this_reward = (this_percentage / 100) * self.app.config['{}.{}.'
                                                                    '{}.{}.reward'
                                                                    ''.format('exchange',
                                                                              'currency',
                                                                              cred[6],
                                                                              cred[5])]
            # Asert almost equal to avoid rounding errors at 10 d.p.
            self.assertAlmostEqual(cred[10], this_reward, 15)
        self.log.debug('ending test_crediting')



