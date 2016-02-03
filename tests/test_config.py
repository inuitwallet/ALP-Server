import json
import logging
import unittest
from os import remove
from os.path import join
import bottle
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
        config.load(self.app, self.log, join('tests', 'config'), log_output=True)

    def test_json_config_btc_reward(self):
        self.assertEqual(self.app.config['test_exchange.btc.reward'], 0.0250)

    def test_json_config_btc_target(self):
        self.assertEqual(self.app.config['test_exchange.btc.target'], 2500)

    def test_json_config_btc_ask_ratio(self):
        self.assertEqual(self.app.config['test_exchange.btc.ask.ratio'], 0.5)

    def test_json_config_btc_ask_rank1_tolerance(self):
        self.assertEqual(self.app.config['test_exchange.btc.ask.rank_1.tolerance'], 0.0105)

    def test_json_config_btc_ask_rank1_ratio(self):
        self.assertEqual(self.app.config['test_exchange.btc.ask.rank_1.ratio'], 1.0)

    def test_json_config_btc_ask_rank2_ratio(self):
        self.assertEqual(self.app.config['test_exchange.btc.ask.rank_2.ratio'], 0.0)

    def test_json_config_btc_bid_ratio(self):
        self.assertEqual(self.app.config['test_exchange.btc.bid.ratio'], 0.5)

    def test_json_config_btc_bid_rank1_tolerance(self):
        self.assertEqual(self.app.config['test_exchange.btc.bid.rank_1.tolerance'], 0.0105)

    def test_json_config_btc_bid_rank1_ratio(self):
        self.assertEqual(self.app.config['test_exchange.btc.bid.rank_1.ratio'], 1.0)

    def test_json_config_btc_bid_rank2_ratio(self):
        self.assertEqual(self.app.config['test_exchange.btc.bid.rank_2.ratio'], 0.0)
        
    def test_json_config_ppc_reward(self):
        self.assertEqual(self.app.config['test_exchange.ppc.reward'], 0.0250)

    def test_json_config_ppc_target(self):
        self.assertEqual(self.app.config['test_exchange.ppc.target'], 1500)

    def test_json_config_ppc_ask_ratio(self):
        self.assertEqual(self.app.config['test_exchange.ppc.ask.ratio'], 0.6)

    def test_json_config_ppc_ask_rank1_tolerance(self):
        self.assertEqual(self.app.config['test_exchange.ppc.ask.rank_1.tolerance'], 0.0105)

    def test_json_config_ppc_ask_rank1_ratio(self):
        self.assertEqual(self.app.config['test_exchange.ppc.ask.rank_1.ratio'], 1.0)

    def test_json_config_ppc_ask_rank2_tolerance(self):
        self.assertEqual(self.app.config['test_exchange.ppc.ask.rank_2.ratio'], 0.0)

    def test_json_config_ppc_bid_ratio(self):
        self.assertEqual(self.app.config['test_exchange.ppc.bid.ratio'], 0.4)

    def test_json_config_ppc_bid_rank1_tolerance(self):
        self.assertEqual(self.app.config['test_exchange.ppc.bid.rank_1.tolerance'], 0.0105)

    def test_json_config_ppc_bid_rank1_ratio(self):
        self.assertEqual(self.app.config['test_exchange.ppc.bid.rank_1.ratio'], 0.8)

    def test_json_config_ppc_bid_rank2_ratio(self):
        self.assertEqual(self.app.config['test_exchange.ppc.bid.rank_2.ratio'], 0.2)

    def test_calculated_config_exchanges(self):
        self.assertListEqual(self.app.config['exchanges'], ['test_exchange'])

    def test_calculated_config_exchange_units(self):
        self.assertListEqual(self.app.config['test_exchange.units'], [u'ppc', u'btc'])

    def test_calculated_config_units(self):
        self.assertListEqual(self.app.config['units'], [u'ppc', u'btc'])

    def test_calculated_config_exchange_btc_ask_ranks(self):
        self.assertListEqual(self.app.config['test_exchange.btc.ask.ranks'], [u'rank_1',
                                                                              u'rank_2'])

    def test_calculated_config_exchange_btc_bid_ranks(self):
        self.assertListEqual(self.app.config['test_exchange.btc.bid.ranks'], [u'rank_1',
                                                                              u'rank_2'])

    def test_calculated_config_exchange_ppc_ask_ranks(self):
        self.assertListEqual(self.app.config['test_exchange.ppc.ask.ranks'], [u'rank_1',
                                                                              u'rank_2'])

    def test_calculated_config_exchange_ppc_ask_ranks(self):
        self.assertListEqual(self.app.config['test_exchange.ppc.bid.ranks'], [u'rank_1',
                                                                              u'rank_2'])

    def build_pool_config_file(self, contents):
        with open('test_pool_config', 'w+') as pool_config:
            pool_config.write(contents)
        pool_config.close()

    def test_pool_config_empty(self):
        self.build_pool_config_file('')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])

    def test_pool_config_no_pool_section(self):
        self.build_pool_config_file(
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\n'
                'port=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No section: 'pool'")

    def test_pool_config_no_rpc_section(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[db]\nname=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\n'
                'host=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No section: 'rpc'")

    def test_pool_config_no_db_section(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No section: 'db'")

    def test_pool_config_no_pool_name(self):
        self.build_pool_config_file(
                '[pool]\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n[rpc]\n'
                'user=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'name' in section: 'pool'")

    def test_pool_config_no_pool_grant_address(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\nminimum_payout=1\n[rpc]\nuser=nu\npass=12345678\n'
                'host=127.0.0.1\nport=14002\n[db]\nname=alp\nuser=alp\n'
                'pass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'grant_address' in section: 'pool'")

    def test_pool_config_no_pool_minimum_payout(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\n[rpc]\nuser=nu\n'
                'pass=12345678\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\nuser=alp\n'
                'pass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'minimum_payout' in section: 'pool'")

    def test_pool_config_no_rpc_user(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'user' in section: 'rpc'")

    def test_pool_config_no_rpc_pass(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\nhost=127.0.0.1\nport=14002\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'pass' in section: 'rpc'")

    def test_pool_config_no_rpc_host(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nport=14002\n[db]\nname=alp\nuser=alp\n'
                'pass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'host' in section: 'rpc'")

    def test_pool_config_no_rpc_port(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\n[db]\nname=alp\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'port' in section: 'rpc'")

    def test_pool_config_no_db_name(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'user=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'name' in section: 'db'")

    def test_pool_config_no_db_user(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'user' in section: 'db'")

    def test_pool_config_no_db_pass(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\nhost=localhost\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'pass' in section: 'db'")

    def test_pool_config_no_db_host(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nport=5432')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'host' in section: 'db'")

    def test_pool_config_no_db_port(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'port' in section: 'db'")

    def test_pool_config_report_first_missing(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\n\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost')
        check = config.check_pool_config('test_pool_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "No option 'grant_address' in section: 'pool'")

    def test_pool_config_full(self):
        self.build_pool_config_file(
                '[pool]\nname=pool\ngrant_address=Bxxxxxxxxxxxxxxxxx\nminimum_payout=1\n'
                '[rpc]\nuser=nu\npass=12345678\nhost=127.0.0.1\nport=14002\n[db]\n'
                'name=alp\nuser=alp\npass=Trip-Tough-Basis-Brother-2\nhost=localhost\n'
                'port=5432')
        self.assertTrue(config.check_pool_config('test_pool_config'))
        remove('test_pool_config')

    def build_exchange_config_file(self, contents):
        """
        Build a test exchange configuration file
        :param contents:
        :return:
        """
        with open('test_exchange_config', 'w+') as exchange_config:
            exchange_config.write(contents)
        exchange_config.close()

    def exchange_test_data(self):
        return json.load(open(join('tests', 'config', 'exchanges', 'test_exchange.json')))

    def test_exchange_config_invalid_json(self):
        self.build_exchange_config_file('{"test": 1234, }')
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'test_exchange_config is not valid json')
        return

    def test_exchange_config_incorrect_exchange(self):
        ex_config = self.exchange_test_data()
        bad_config = {'bad_exchange': ex_config['test_exchange']}
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'bad_exchange is not a supported exchange')

    def test_exchange_config_no_reward(self):
        bad_config = self.exchange_test_data()
        del bad_config['test_exchange']['btc']['reward']
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'There is no reward set for test_exchange.btc')

    def test_exchange_config_zero_reward(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['reward'] = 0
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The reward set for test_exchange.btc is incorrect')

    def test_exchange_config_negative_reward(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['reward'] = -1234
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The reward set for test_exchange.btc is incorrect')

    def test_exchange_no_target(self):
        bad_config = self.exchange_test_data()
        del bad_config['test_exchange']['btc']['target']
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'There is no target set for test_exchange.btc')

    def test_exchange_config_zero_target(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['target'] = 0
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The target set for test_exchange.btc is incorrect')

    def test_exchange_config_negative_target(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['target'] = -1234
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The target set for test_exchange.btc is incorrect')

    def test_exchange_config_no_ask(self):
        bad_config = self.exchange_test_data()
        del bad_config['test_exchange']['btc']['ask']
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "test_exchange.btc has no 'ask' details")

    def test_exchange_config_no_bid(self):
        bad_config = self.exchange_test_data()
        del bad_config['test_exchange']['btc']['bid']
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "test_exchange.btc has no 'bid' details")

    def test_exchange_config_no_ask_ratio(self):
        bad_config = self.exchange_test_data()
        del bad_config['test_exchange']['btc']['ask']['ratio']
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'There is no ratio set for test_exchange.btc.ask')

    def test_exchange_config_zero_ask_ratio(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['ask']['ratio'] = 0
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The ratio set for test_exchange.btc.ask is incorrect')

    def test_exchange_config_negative_ask_ratio(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['ask']['ratio'] = -1234
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The ratio set for test_exchange.btc.ask is incorrect')

    def test_exchange_config_no_bid_ratio(self):
        bad_config = self.exchange_test_data()
        del bad_config['test_exchange']['btc']['bid']['ratio']
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'There is no ratio set for test_exchange.btc.bid')

    def test_exchange_config_zero_bid_ratio(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['bid']['ratio'] = 0
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The ratio set for test_exchange.btc.bid is incorrect')

    def test_exchange_config_negative_bid_ratio(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['bid']['ratio'] = -1234
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], 'The ratio set for test_exchange.btc.bid is incorrect')

    def test_exchange_config_ask_bid_ratio(self):
        bad_config = self.exchange_test_data()
        bad_config['test_exchange']['btc']['ask']['ratio'] = 0.6
        bad_config['test_exchange']['btc']['bid']['ratio'] = 0.6
        self.build_exchange_config_file(json.dumps(bad_config))
        check = config.check_exchange_config('test_exchange_config')
        self.assertFalse(check[0])
        self.assertEqual(check[1], "The ask and bid ratios don't add up to 1.0")

    def test_exchange_config_full(self):
        full_config = self.exchange_test_data()
        self.build_exchange_config_file(json.dumps(full_config))
        check = config.check_exchange_config('test_exchange_config')
        print check
        self.assertTrue(check[0])
        remove('test_exchange_config')
