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

log.debug('test root url')
resp = app.get('/')
assert resp.json == {'success': True, 'message': 'ALP Server is operational'}

log.debug('test register without correct headers')
resp = app.post('/register')
assert resp.json == {'success': False, 'message': 'Content-Type header must be '
                                                  'set to \'application/json\''}
log.debug('test register with no data')
resp = app.post('/register', headers=headers)
assert resp.json == {'success': False, 'message': 'no json found in request'}

log.debug('test register with blank data')
resp = app.post('/register', headers=headers, params={})

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
data['address'] = 'BMJ2PJ1TNMwnTYUopQVxBraPmmJjJjhd95'
resp = app.post('/register', headers=headers, params=json.dumps(data))
assert resp.json == {'success': False, 'message': 'BMJ2PJ1TNMwnTYUopQVxBraPmmJjJjhd95 '
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
