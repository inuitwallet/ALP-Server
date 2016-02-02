import json
import logging
import unittest

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
        """
        Root
        """
        self.log.debug('test root url')
        resp = self.app.get('/')
        self.assertDictEqual(resp.json,
                             {'success': True, 'message': 'ALP Server is operational'})

    def test_register(self):
        """
        Register
        :return:
        """
        self.log.debug('test register without correct headers')
        self.assertDictEqual(self.app.post('/register').json,
                             {'success': False,
                              'message': 'Content-Type header must be set to '
                                         '\'application/json\''})
        self.log.debug('test register with no data')
        self.assertDictEqual(self.app.post('/register', headers=self.headers).json,
                             {'success': False, 
                              'message': 'request body must be valid json'})
        self.log.debug('test register with blank data')
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers, params={}).json,
                             {'success': False,
                              'message': 'request body must be valid json'})
        self.log.debug('test register with invalid json')
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params='{"user": "abcd123", }').json,
                             {'success': False,
                              'message': 'request body must be valid json'})
        self.log.debug('set test data')
        test_data = {'user': 'TEST_USER_1', 'address': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96',
                     'exchange': 'test_exchange', 'unit': 'btc'}
        self.log.debug('test register with no user in data')
        data = test_data.copy()
        del data['user']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no user provided'})
        self.log.debug('test register with no address in data')
        data = test_data.copy()
        del data['address']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no address provided'})
        self.log.debug('test register with no exchange in data')
        data = test_data.copy()
        del data['exchange']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no exchange provided'})
        self.log.debug('test register with no unit in data')
        data = test_data.copy()
        del data['unit']
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no unit provided'})
        self.log.debug('test register with invalid address in data (no B at start)')
        data = test_data.copy()
        data['address'] = 'JMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': "JMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96 is not a "
                                         "valid NBT address. It should start with a 'B'"})
        self.log.debug('test register with invalid address in data (invalid checksum)')
        data = test_data.copy()
        data['address'] = 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd95'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': "BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd95 is not a "
                                         "valid NBT address. The checksum doesn't match"})
        self.log.debug('test register with unsupported exchange')
        data = test_data.copy()
        data['exchange'] = 'bad_exchange'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': 'bad_exchange is not supported'})
        self.log.debug('test register with unsupported unit')
        data = test_data.copy()
        data['unit'] = 'bad_unit'
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': 'bad_unit is not supported on test_exchange'})
        self.log.debug('test register complete')
        data = test_data.copy()
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': True, 'message': 'user successfully registered'})
        self.log.debug('test register re-register')
        data = test_data.copy()
        self.assertDictEqual(self.app.post('/register',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'user is already registered'})

    def test_liquidity(self):
        """
        Liquidity
        :return:
        """
        self.log.debug('test liquidity without correct headers')
        self.assertDictEqual(self.app.post('/liquidity').json,
                             {'success': False,
                              'message': 'Content-Type header must be set to '
                                         '\'application/json\''})
        self.log.debug('test liquidity with no data')
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers).json,
                             {'success': False,
                             'message': 'request body must be valid json'})
        self.log.debug('test liquidity with blank data')
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers, params={}).json,
                             {'success': False,
                             'message': 'request body must be valid json'})
        self.log.debug('test liquidity with invalid json')
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params='{"user", "as234", }').json,
                             {'success': False,
                              'message': 'request body must be valid json'})
        self.log.debug('set test data')
        test_data = {'user': 'TEST_USER_1', 'req': {'test': True},
                     'sign': 'this_is_signed',
                     'exchange': 'test_exchange', 'unit': 'btc'}
        self.log.debug('test liquidity with no user')
        data = test_data.copy()
        del data['user']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no user provided'})
        self.log.debug('test liquidity with no req')
        data = test_data.copy()
        del data['req']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no req provided'})
        self.log.debug('test liquidity with no sign')
        data = test_data.copy()
        del data['sign']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no sign provided'})
        self.log.debug('test liquidity with no exchange')
        data = test_data.copy()
        del data['exchange']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no exchange provided'})
        self.log.debug('test liquidity with no unit')
        data = test_data.copy()
        del data['unit']
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False, 'message': 'no unit provided'})
        self.log.debug('test liquidity with incorrect user')
        data = test_data.copy()
        data['user'] = 'blahblahblah'
        self.assertDictEqual(self.app.post('/liquidity',
                                           headers=self.headers,
                                           params=json.dumps(data)).json,
                             {'success': False,
                              'message': 'user blahblahblah is not registered'})
        self.log.debug('test liquidity complete')
        reg_data = {'user': 'TEST_USER_1',
                    'address': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96',
                    'exchange': 'test_exchange', 'unit': 'btc'}
        self.app.post('/register', headers=self.headers, params=json.dumps(reg_data))
        data = test_data.copy()
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
                        u'ratio': 0.6,
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
