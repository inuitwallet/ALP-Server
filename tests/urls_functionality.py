import json
import logging
import os
from webtest import TestApp
import sys
sys.path.append('../')
if os.path.isfile('pool.db'):
    os.remove('pool.db')
import pool_server

__author__ = 'sammoth'

log = logging.Logger('ALP_Test')
stream = logging.StreamHandler()
formatter = logging.Formatter(fmt='%(message)s')
stream.setFormatter(formatter)
log.addHandler(stream)

app = TestApp(pool_server.app)

headers = {'Content-Type': 'application/json'}

########
# # Root
########

log.debug('test root url')
resp = app.get('/')
assert resp.json == {'success': True, 'message': 'ALP Server is operational'}

########
# # Register
########

log.debug('test register without correct headers')
resp = app.post('/register')
assert resp.json == {'success': False, 'message': 'Content-Type header must be '
                                                  'set to \'application/json\''}
log.debug('test register with no data')
resp = app.post('/register', headers=headers)
assert resp.json == {'success': False, 'message': 'request body must be valid json'}

log.debug('test register with blank data')
resp = app.post('/register', headers=headers, params={})
assert resp.json == {'success': False, 'message': 'request body must be valid json'}

log.debug('test register with invalid json')
resp = app.post('/register', headers=headers, params='{"user": "abcd123", }')
assert resp.json == {'success': False, 'message': 'request body must be valid json'}

log.debug('set test data')
test_data = {'user': 'TEST_USER_1', 'address': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96',
             'exchange': 'test_exchange', 'unit': 'btc'}

log.debug('test register with no user in data')
data = test_data.copy()
del data['user']
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no user provided'}

log.debug('test register with no address in data')
data = test_data.copy()
del data['address']
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no address provided'}

log.debug('test register with no exchange in data')
data = test_data.copy()
del data['exchange']
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no exchange provided'}

log.debug('test register with no unit in data')
data = test_data.copy()
del data['unit']
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no unit provided'}

log.debug('test register with invalid address in data (no B at start)')
data = test_data.copy()
data['address'] = 'JMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96'
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'JMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96 '
                                                  'is not a valid NBT address. It '
                                                  'should start with a \'B\''}

log.debug('test register with invalid address in data (invalid checksum)')
data = test_data.copy()
data['address'] = 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd95'
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd95 '
                                                  'is not a valid NBT address. The '
                                                  'checksum doesn\'t match'}

log.debug('test register with unsupported exchange')
data = test_data.copy()
data['exchange'] = 'bad_exchange'
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'bad_exchange is not supported'}

log.debug('test register with unsupported unit')
data = test_data.copy()
data['unit'] = 'bad_unit'
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'bad_unit is not supported on '
                                                  'test_exchange'}

log.debug('test register complete')
data = test_data.copy()
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': True, 'message': 'user successfully registered'}

log.debug('test register reregister')
data = test_data.copy()
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'user is already registered'}

#######
# # Liquidity
#######

log.debug('test liquidity without correct headers')
resp = app.post('/liquidity')
assert resp.json == {'success': False, 'message': 'Content-Type header must be '
                                                  'set to \'application/json\''}
log.debug('test liquidity with no data')
resp = app.post('/liquidity', headers=headers)
assert resp.json == {'success': False, 'message': 'request body must be valid json'}

log.debug('test liquidity with blank data')
resp = app.post('/liquidity', headers=headers, params={})
assert resp.json == {'success': False, 'message': 'request body must be valid json'}

log.debug('test liquidity with invalid json')
resp = app.post('/liquidity', headers=headers, params='{"user", "as234", }')

log.debug('set test data')
test_data = {'user': 'TEST_USER_1', 'req': {'test': True}, 'sign': 'this_is_signed',
             'exchange': 'test_exchange', 'unit': 'btc'}

log.debug('test liquidity with no user')
data = test_data.copy()
del data['user']
resp = app.post('/liquidity', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no user provided'}

log.debug('test liquidity with no req')
data = test_data.copy()
del data['req']
resp = app.post('/liquidity', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no req provided'}

log.debug('test liquidity with no sign')
data = test_data.copy()
del data['sign']
resp = app.post('/liquidity', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no sign provided'}

log.debug('test liquidity with no exchange')
data = test_data.copy()
del data['exchange']
resp = app.post('/liquidity', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no exchange provided'}

log.debug('test liquidity with no unit')
data = test_data.copy()
del data['unit']
resp = app.post('/liquidity', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'no unit provided'}

log.debug('test liquidity complete')
data = test_data.copy()
resp = app.post('/liquidity', headers=headers, params=json.dumps(data))
assert resp.json == {'success': True, 'message': 'orders saved for validation'}

if os.path.isfile('pool.db'):
    os.remove('pool.db')
