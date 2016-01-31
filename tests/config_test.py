import logging
import sys
import unittest

from os.path import join

import bottle
sys.path.append('../')
from src import config


class TestConfig(unittest.TestCase):

    def setUp(self):
        """
        Load the config
        :return:
        """
        # Build the tests Logger
        self.log = logging.Logger('Tests')
        stream = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(message)s')
        stream.setFormatter(formatter)
        self.log.addHandler(stream)
        self.app = bottle.Bottle()
        config.load(self.app, self.log, join('..', 'tests', 'config'), log_output=True)

    def test_json_config_is_correct(self):
        self.log.info('check test_exchange.btc.reward')
        self.assertEqual(self.app.config['test_exchange.btc.reward'], 0.0250)
        self.log.info('check test_exchange.btc.target')
        self.assertEqual(self.app.config['test_exchange.btc.target'], 2500)
        self.log.info('check test_exchange.btc.ask.ratio')
        self.assertEqual(self.app.config['test_exchange.btc.ask.ratio'], 0.5)
        self.log.info('check test_exchange.btc.ask.rank_1.tolerance')
        self.assertEqual(self.app.config['test_exchange.btc.ask.rank_1.tolerance'], 0.0105)
        self.log.info('check test_exchange.btc.ask.rank_1.ratio')
        self.assertEqual(self.app.config['test_exchange.btc.ask.rank_1.ratio'], 1.0)
        self.log.info('check test_exchange.btc.ask.rank_2.ratio')
        self.assertEqual(self.app.config['test_exchange.btc.ask.rank_2.ratio'], 0.0)
        self.log.info('check test_exchange.btc.bid.ratio')
        self.assertEqual(self.app.config['test_exchange.btc.bid.ratio'], 0.5)
        self.log.info('check test_exchange.btc.bid.rank_1.tolerance')
        self.assertEqual(self.app.config['test_exchange.btc.bid.rank_1.tolerance'], 0.0105)
        self.log.info('check test_exchange.btc.bid.rank_1.ratio')
        self.assertEqual(self.app.config['test_exchange.btc.bid.rank_1.ratio'], 1.0)
        self.log.info('check test_exchange.btc.bid.rank_2.ratio')
        self.assertEqual(self.app.config['test_exchange.btc.bid.rank_2.ratio'], 0.0)
        
        self.log.info('check test_exchange.ppc.reward')
        self.assertEqual(self.app.config['test_exchange.ppc.reward'], 0.0250)
        self.log.info('check test_exchange.ppc.target')
        self.assertEqual(self.app.config['test_exchange.ppc.target'], 1500)
        self.log.info('check test_exchange.ppc.ask.ratio')
        self.assertEqual(self.app.config['test_exchange.ppc.ask.ratio'], 0.6)
        self.log.info('check test_exchange.ppc.ask.rank_1.tolerance')
        self.assertEqual(self.app.config['test_exchange.ppc.ask.rank_1.tolerance'], 0.0105)
        self.log.info('check test_exchange.ppc.ask.rank_1.ratio')
        self.assertEqual(self.app.config['test_exchange.ppc.ask.rank_1.ratio'], 1.0)
        self.log.info('check test_exchange.ppc.ask.rank_2.ratio')
        self.assertEqual(self.app.config['test_exchange.ppc.ask.rank_2.ratio'], 0.0)
        self.log.info('check test_exchange.ppc.bid.ratio')
        self.assertEqual(self.app.config['test_exchange.ppc.bid.ratio'], 0.4)
        self.log.info('check test_exchange.ppc.bid.rank_1.tolerance')
        self.assertEqual(self.app.config['test_exchange.ppc.bid.rank_1.tolerance'], 0.0105)
        self.log.info('check test_exchange.ppc.bid.rank_1.ratio')
        self.assertEqual(self.app.config['test_exchange.ppc.bid.rank_1.ratio'], 0.8)
        self.log.info('check test_exchange.ppc.bid.rank_2.ratio')
        self.assertEqual(self.app.config['test_exchange.ppc.bid.rank_2.ratio'], 0.2)

    def test_calculated_config_is_correct(self):
        self.log.info('check exchanges')
        self.assertListEqual(self.app.config['exchanges'], ['test_exchange'])
        self.log.info('check test_exchange.units')
        self.assertListEqual(self.app.config['test_exchange.units'], [u'ppc', u'btc'])
        self.log.info('check units')
        self.assertListEqual(self.app.config['units'], [u'ppc', u'btc'])
        self.log.info('check test_exchange.btc.ask.ranks')
        self.assertListEqual(self.app.config['test_exchange.btc.ask.ranks'], [u'rank_1',
                                                                              u'rank_2'])
        self.log.info('check test_exchange.btc.bid.ranks')
        self.assertListEqual(self.app.config['test_exchange.btc.bid.ranks'], [u'rank_1',
                                                                              u'rank_2'])
        self.log.info('check test_exchange.ppc.ask.ranks')
        self.assertListEqual(self.app.config['test_exchange.ppc.ask.ranks'], [u'rank_1',
                                                                              u'rank_2'])
        self.log.info('check test_exchange.ppc.bid.ranks')
        self.assertListEqual(self.app.config['test_exchange.ppc.bid.ranks'], [u'rank_1',
                                                                              u'rank_2'])
