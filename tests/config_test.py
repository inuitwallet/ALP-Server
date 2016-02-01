import logging
import sys
import unittest
from os import remove
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

    def build_pool_config_file(self, contents):
        with open('test_pool_config', 'w+') as pool_config:
            pool_config.write(contents)
        pool_config.close()

    def test_check_pool_config(self):
        self.log.info('test pool config checks')
        self.log.info('empty config')
        self.build_pool_config_file('')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.log.info('missing pool section')
        self.build_pool_config_file(
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\n'
                'port=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No section: 'pool'")
        self.log.info('missing rpc section')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[db]\nname=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\n'
                'host=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No section: 'rpc'")
        self.log.info('missing db section')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No section: 'db'")
        self.log.info('missing pool name')
        self.build_pool_config_file(
                '[pool]\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n[rpc]\n'
                'user=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'name' in section: 'pool'")
        self.log.info('missing pool grant address')
        self.build_pool_config_file(
                '[pool]\nname=pool\nminimum_payout=1\n[rpc]\nuser=nu\npass=12345678\n'
                'host=127.0.0.1\nport=14002\n[db]\nname=alp\nuser=alp\n'
                'pass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'grant_address' in section: 'pool'")
        self.log.info('missing pool minimum payout')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\n[rpc]\nuser=nu\n'
                'pass=12345678\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\nuser=alp\n'
                'pass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'minimum_payout' in section: 'pool'")
        self.log.info('missing rpc user')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'user' in section: 'rpc'")
        self.log.info('missing rpc pass')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'pass' in section: 'rpc'")
        self.log.info('missing rpc host')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nport=14002\n[db]\nname=alp\nuser=alp\n'
                'pass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'host' in section: 'rpc'")
        self.log.info('missing rpc port')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'port' in section: 'rpc'")
        self.log.info('missing db name')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'name' in section: 'db'")
        self.log.info('missing db user')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'user' in section: 'db'")
        self.log.info('missing db pass')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'pass' in section: 'db'")
        self.log.info('missing db host')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'host' in section: 'db'")
        self.log.info('missing db port')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'port' in section: 'db'")
        self.log.info('report first missing')
        self.build_pool_config_file(
                '[pool]\nname=pool\n\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'grant_address' in section: 'pool'")
        self.log.info('full config')
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\n'
                'port=5432')
        self.assertTrue(config.check_pool_config('test_pool_config'))
        remove('test_pool_config')
