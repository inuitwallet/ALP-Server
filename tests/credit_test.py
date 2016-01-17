import logging
import sys
import unittest

import time

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
        # set us up a bottle application with correct config
        self.app = bottle.Bottle()
        self.app.config.load_config('config/pool_config')
        config.load(self.app, self.log, log_output=False)
        # build the database if it doesn't exist
        database.build(self.app, self.log, log_output=False)
        # clear any existing orders in the database
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("DELETE FROM orders")
        c.execute("DELETE FROM credits")
        conn.commit()
        # create test data
        # 5 test users each with 100 NBT on each exchange/pair/side/rank
        self.test_data = {}
        test_order_number = 1
        for i in xrange(0, 5):
            for unit in ['btc', 'ppc']:
                for side in ['ask','bid']:
                    for rank in ['rank_1', 'rank_2']:
                        c.execute("INSERT INTO orders (key,rank,order_id,order_amount,"
                                  "side,exchange,unit,credited) VALUES "
                                  "(%s,%s,%s,%s,%s,%s,%s,%s)",
                                  ('TEST_USER_{}'.format(i + 1), rank, test_order_number,
                                   100, side, 'test_exchange', unit, 0))
                        test_order_number += 1
        conn.commit()
        conn.close()

        # setup test data for test_get_total_liquidity]
        # get the orders from the database
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("SELECT * FROM orders")
        orders = c.fetchall()
        # get the liquidity as calculated by the main function
        self.total_liquidity = credit.get_total_liquidity(self.app, orders)

        # setup data for test_calculate_rewards
        # target for btc is 2500. total for btc is 2000.0 which is 0.8 of target
        # so already reward for btc is 0.02 instead of 0.025
        # ask and bid are 50:50 so each gets 0.01. rank_1 ratio is 1.0 and rank_2 is 0 for
        # both.
        #
        # target for ppc is 1500. total for ppc is 2000.0 so full reward of 0.0250
        # ask is 0.6 * 0.025 = 0.015
        # bid is 0.4 * 0.025 = 0.010
        # ask rank_1 is 1
        # bid rank_1 is 0.8 * 0.010 = 0.008
        # bid rank_2 is 0.2 * 0.010 = 0.002
        self.rewards = {'test_exchange': {'btc': {'ask': {'rank_1': 0.01,
                                                          'rank_2': 0.0},
                                                  'bid': {'rank_1': 0.01,
                                                          'rank_2': 0.0}
                                                  },

                                          'ppc': {'ask': {'rank_1': 0.015,
                                                          'rank_2': 0.0},
                                                  'bid': {'rank_1': 0.008,
                                                          'rank_2': 0.002}}}}

    def test_get_total_liquidity(self):
        """
        Test the get_total_liquidity function
        :return:
        """
        self.log.debug('running test_get_total_liquidity')
        self.assertDictEqual(self.total_liquidity,
                             {'test_exchange': {'ppc': {'ask': {'total': 1000.0,
                                                                'rank_1': 500.0,
                                                                'rank_2': 500.0},
                                                        'bid': {'total': 1000.0,
                                                                'rank_1': 500.0,
                                                                'rank_2': 500.0},
                                                        'total': 2000.0},
                                                'btc': {'ask': {'total': 1000.0,
                                                                'rank_1': 500.0,
                                                                'rank_2': 500.0},
                                                        'bid': {'total': 1000.0,
                                                                'rank_1': 500.0,
                                                                'rank_2': 500.0},
                                                        'total': 2000.0}}})

    def test_calculate_reward(self):
        """
        Test the calculate_reward function
        :return:
        """
        self.log.debug('running test_calculate_reward')
        self.assertDictEqual(credit.calculate_reward(self.app, self.total_liquidity),
                             self.rewards)

    def test_calculate_order_reward(self):
        """
        Test the reward calculation for each order
        :return:
        """
        self.log.debug('running order reward calculation')
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("SELECT * FROM orders")
        all_orders = c.fetchall()
        # we know there are no duplicate orders in the test data
        # each order is 100 NBT
        # total for each side/rank is 500
        # therefore each order is 0.2 * reward
        for order in all_orders:
            order_reward = credit.calculate_order_reward(self.app, order,
                                                         self.total_liquidity,
                                                         self.rewards)
            calc_reward = (float(self.rewards[order[8]][order[9]][order[5]][order[2]]) *
                           0.2)
            self.assertEqual(order_reward[0], calc_reward)

    def test_crediting(self):
        """
        Test the credit function
        :return:
        """
        self.log.debug('running test_crediting')

        # for crediting we expect the credit output to look like
        check_time = int(time.time())
        credit.credit(self.app, None, self.log)
        # get the credit details from the database
        conn = database.get_db(self.app)
        c = conn.cursor()
        c.execute("SELECT * FROM credits")
        credit_data = c.fetchall()
        # self.log.debug(credit_data)
        # check the credits are correct
        for cred in credit_data:
            # check the time is about right
            self.assertAlmostEqual(cred[1], check_time)
            # check the user isn't something random
            self.assertIn(cred[2], ['TEST_USER_1', 'TEST_USER_2', 'TEST_USER_3',
                                    'TEST_USER_4', 'TEST_USER_5'])
            # check the exchange is good
            self.assertEqual(cred[3], 'test_exchange')
            # check unit, side and rank
            self.assertIn(cred[4], ['btc', 'ppc'])
            self.assertIn(cred[5], ['rank_1', 'rank_2'])
            self.assertIn(cred[6], ['ask', 'bid'])
            # check the amount provided
            self.assertEqual(cred[8], 100)
            # check the percentage
            self.assertEqual(cred[9], 20)
            # check the reward
            self.assertEqual(cred[10],
                             float(self.rewards[cred[3]][cred[4]][cred[6]][cred[5]]) *
                             0.2)
            self.assertEqual(cred[11], 0)
