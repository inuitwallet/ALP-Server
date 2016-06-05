import json
import logging
import unittest

import time

import os
from os.path import join
from src import database
from webtest import TestApp

__author__ = 'sammoth'


class TestUrls(unittest.TestCase):

    def setUp(self):
        """
        Load the config
        :return:
        """
        self.log = logging.Logger('ALP_Test')
        stream = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(message)s')
        stream.setFormatter(formatter)
        self.log.addHandler(stream)
        os.environ['CONFIG_DIR'] = join('tests', 'config')
        import pool_server
        app = pool_server.app
        self.app = TestApp(app)

        self.headers = {'Content-Type': 'application/json'}
        # clear TEST_USER_1
        conn = database.get_db(app)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE key='TEST_USER_1'")
        conn.commit()
        conn.close()

    def test_root(self):
        resp = self.app.get('/')
        self.assertDictEqual(resp.json,
                             {'success': True, 'message': 'ALP Server is operational'})

    def test_register_without_correct_headers(self):
        self.assertDictEqual(self.app.post('/register').json,
                             {'success': False,
                              'message': 'Content-Type header must be set to '
                                         '\'application/json\''})

    def test_register_without_no_data(self):
        self.assertDictEqual(self.app.post('/register', headers=self.headers).json,
                             {'success': False, 
                              'message': 'request body must be valid json'})

    def test_register_without_blank_data(self):
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers, params={}).json,
                             {'success': False,
                              'message': 'request body must be valid json'})

    def test_register_without_invalid_json(self):
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params='{"user": "abcd123", }').json,
                             {'success': False,
                              'message': 'request body must be valid json'})

    def register_test_data(self):
        return {'user': 'TEST_USER_1', 'address': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96',
                'exchange': 'test_exchange', 'unit': 'btc'}

    def test_register_no_user(self):
        data = self.register_test_data()
        del data['user']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no user provided'})

    def test_register_no_address(self):
        data = self.register_test_data()
        del data['address']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no address provided'})

    def test_register_no_exchange(self):
        data = self.register_test_data()
        del data['exchange']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no exchange provided'})

    def test_register_no_unit(self):
        data = self.register_test_data()
        del data['unit']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no unit provided'})

    def test_register_invalid_address_no_B(self):
        data = self.register_test_data()
        data['address'] = 'JMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': "JMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96 is not a "
                                         "valid NBT address. It should start with a 'B'"})

    def test_register_invalid_address_bad_checksum(self):
        data = self.register_test_data()
        data['address'] = 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd95'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': "BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd95 is not a "
                                         "valid NBT address. The checksum doesn't match"})

    def test_register_unsupported_exchange(self):
        data = self.register_test_data()
        data['exchange'] = 'bad_exchange'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': 'bad_exchange is not supported'})

    def test_register_unsupported_unit(self):
        data = self.register_test_data()
        data['unit'] = 'bad_unit'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': 'bad_unit is not supported on test_exchange'})

    def test_register_complete(self):
        data = self.register_test_data()
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': True, 'message': 'user successfully registered'})
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'user is already registered'})

    def test_liquidity_without_correct_headers(self):
        self.assertDictEqual(self.app.post('/liquidity').json,
                             {'success': False,
                              'message': 'Content-Type header must be set to '
                                         '\'application/json\''})

    def test_liquidity_no_data(self):
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers).json,
                             {'success': False,
                             'message': 'request body must be valid json'})

    def test_liquidity_blank_data(self):
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers, params={}).json,
                             {'success': False,
                             'message': 'request body must be valid json'})

    def test_liquidity_invalid_json(self):
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params='{"user", "as234", }').json,
                             {'success': False,
                              'message': 'request body must be valid json'})

    def liquidity_test_data(selfself):
        return {'user': 'TEST_USER_1', 'req': {'test': True}, 'sign': 'this_is_signed',
                'exchange': 'test_exchange', 'unit': 'btc'}

    def test_liquidity_no_user(self):
        data = self.liquidity_test_data()
        del data['user']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no user provided'})

    def test_liquidity_no_req(self):
        data = self.liquidity_test_data()
        del data['req']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no req provided'})

    def test_liquidity_no_sign(self):
        data = self.liquidity_test_data()
        del data['sign']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no sign provided'})

    def test_liquidity_no_exchange(self):
        data = self.liquidity_test_data()
        del data['exchange']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no exchange provided'})

    def test_liquidity_no_unit(self):
        data = self.liquidity_test_data()
        del data['unit']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no unit provided'})

    def test_liquidity_incorrect_user(self):
        data = self.liquidity_test_data()
        data['user'] = 'blahblahblah'
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': 'user blahblahblah is not registered'})

    def test_liquidity_complete(self):
        data = self.liquidity_test_data()
        reg_data = {'user': 'TEST_USER_1',
                    'address': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96',
                    'exchange': 'test_exchange', 'unit': 'btc'}
        self.app.post('/register', headers=self.headers, params=json.dumps(reg_data))
        while self.app.post(
                '/liquidity',
                headers=self.headers,
                params=json.dumps(data)
            ).json == {
            'message': 'unable to fetch current price for btc',
            'success': False
        }:
            time.sleep(10)
            continue
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': True, 'message': 'orders saved for validation'})

    def test_exchanges(self):
        """
        Exchanges
        :return:
        """
        self.log.debug('test exchanges stats')
        self.assertDictEqual(self.app.get('/exchanges').json, {
            u'test_exchange': {
                u'ppc': {
                    u'ask': {
                        u'ratio': 0.6,
                        u'rank_1': {
                            u'ratio': 1.0,
                            u'tolerance': 0.0105
                        },
                        u'rank_2': {
                            u'ratio': 0.0,
                            u'tolerance': 1.0}
                    },
                    u'bid': {
                        u'ratio': 0.4,
                        u'rank_1': {
                            u'ratio': 0.8,
                            u'tolerance': 0.0105
                        },
                        u'rank_2': {
                            u'ratio': 0.2,
                            u'tolerance': 1.0
                        }
                    },
                    u'reward': 0.025,
                    u'target': 1500
                },
                u'btc': {
                    u'ask': {
                        u'ratio': 0.5,
                        u'rank_1': {
                            u'ratio': 1.0,
                            u'tolerance': 0.0105
                        },
                        u'rank_2': {
                            u'ratio': 0.0,
                            u'tolerance': 1.0
                        }
                    },
                    u'bid': {
                        u'ratio': 0.5,
                        u'rank_1': {
                            u'ratio': 1.0,
                            u'tolerance': 0.0105
                        },
                        u'rank_2': {
                            u'ratio': 0.0,
                            u'tolerance': 1.0
                        }
                    },
                    u'reward': 0.025,
                    u'target': 2500
                }
            }
        })
