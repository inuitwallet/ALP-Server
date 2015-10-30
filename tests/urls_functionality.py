from webtest import TestApp
import sys

sys.path.append('../')
import pool_server

__author__ = 'sammoth'


app = TestApp(pool_server.app)

headers = {'Content-Type': 'application/json'}

# test root url
resp = app.get('/')
assert resp.json == {'success': True, 'message': 'ALP Server is operational'}

# test register without correct headers
resp = app.post('/register')
assert resp.json == {'success': False, 'message': 'Content-Type header must be '
                                                  'set to \'application/json\''}
# test register with no data
resp = app.post('/register', headers=headers)
assert resp.json == {'success': False, 'message': 'no json found in request'}

# test register with blank data
resp = app.post('/register', headers=headers, params={})

# set test data
test_data = {'user': 'TEST_USER_1', 'address': 'BMJ2PJ1TNMwnTYUopQVxBrAPmmJjJjhd96',
             'exchange': 'exchange', 'unit': 'currency'}

# test register with no user in data
data = test_data.copy()
del data['user']
print data
resp = app.post('/register', headers=headers, params=data)
assert resp.json == {'success': False, 'message': 'no user provided'}
