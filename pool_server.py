import sqlite3
from threading import Timer, Thread

import bottle
from bottle_sqlite import SQLitePlugin
from bottle import run, request
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import credit
from payout import pay
import database
import load_config
from utils import AddressCheck
from exchanges import *

__author__ = 'sammoth'

app = bottle.Bottle()

# Load the pool config
app.config.load_config('pool_config')

# Load the exchange config
load_config.load(app)

# Create the database if one doesn't exist
database.build()

# Install the SQLite plugin
app.install(SQLitePlugin(dbfile='pool.db', keyword='db'))

# Create the Exchange wrapper objects
wrappers = {'bittrex': Bittrex(), 'bter': BTER(), 'ccedk': CCEDK()}

# Set up a JSONRPC connection to nud
rpc = AuthServiceProxy("http://{}:{}@{}:{}".format(app.config['rpc.user'],
                                                   app.config['rpc.pass'],
                                                   app.config['rpc.host'],
                                                   app.config['rpc.port']))


def check_headers(headers):
    """
    Ensure the correct headers get passed in the request
    :param headers:
    :return:
    """
    if headers.get('Content-Type') != 'application/json':
        return False
    return True


@app.post('/register')
def register(db):
    """
    Register a new user on the server
    Requires:
        user - API public Key
        address - Valid NBT payout address
        exchange - supported exchange
        unit - supported currency
    :return:
    """
    # Check the content type
    if not check_headers(request.headers):
        return {'success': False, 'message': 'Content-Type header must be set to '
                                             '\'application/json\''}
    # Get the post parameters
    try:
        user = request.json.get('user')
        address = request.json.get('address')
        exchange = request.json.get('exchange')
        unit = request.json.get('unit')
    except ValueError:
        return {'success': False, 'message': 'no json found in request'}
    # check for missing parameters
    if not user:
        return {'success': False, 'message': 'no user provided'}
    if not address:
        return {'success': False, 'message': 'no address provided'}
    if not exchange:
        return {'success': False, 'message': 'no exchange provided'}
    if not unit:
        return {'success': False, 'message': 'no unit provided'}
    # Check for a valid address
    address_check = AddressCheck()
    if address[0] != 'B' and not address_check.check_checksum(address):
        return {'success': False, 'message': '{} is not a valid NBT address'.format(
            address)}
    # Check that the requests exchange is supported by the server
    if exchange not in app.config['exchanges']:
        return {'success': False, 'message': '{} is not supported'.format(exchange)}
    # Check that the unit is supported on the server
    if unit not in app.config['{}.units'.format(exchange)]:
        return {'success': False, 'message': '{} is not supported on {}'.format(unit,
                                                                                exchange)}
    # Check if the user already exists in the database
    check = db.execute("SELECT id FROM users WHERE user=? AND address=? AND "
                       "exchange=? AND unit=?;", (user, address, exchange,
                                                  unit)).fetchone()
    if check:
        return {'success': False, 'message': 'user is already registered'}
    db.execute("INSERT INTO users ('user','address','exchange','unit') VALUES (?,?,?,?)",
               (user, address, exchange, unit))
    return {'success': True, 'message': 'user successfully registered'}


@app.post('/liquidity')
def liquidity(db):
    """
    Allow the user to submit liquidity validations to the server
    Will be multiple times per minute
    With the submitted data get the users orders and update the database accordingly
    Requires:
        user - API public Key
        req - dictionary to be used to get open orders
        sign - result of signing req with API private key
        exchange - valid, supported exchange
        unit - valid, supported unit
    :return:
    """
    # Check the content type
    if not check_headers(request.headers):
        return {'success': False, 'message': 'Content-Type header must be set to '
                                             '\'application/json\''}
    # Get the post parameters
    try:
        user = request.json.get('user')
        sign = request.json.get('sign')
        exchange = request.json.get('exchange')
        unit = request.json.get('unit')
        req = request.json.get('req')
    except ValueError:
        return {'success': False, 'message': 'no json found in request'}
    if not user:
        return {'success': False, 'message': 'no user provided'}
    if not sign:
        return {'success': False, 'message': 'no sign provided'}
    if not exchange:
        return {'success': False, 'message': 'no exchange provided'}
    if not unit:
        return {'success': False, 'message': 'no unit provided'}
    if not req:
        return {'success': False, 'message': 'no req provided'}
    # use the submitted data to request the users orders
    #orders = wrappers[exchange].validate_request(user, unit, req, sign)
    orders = build_order_list()
    price = get_price()
    # clear existing orders for the user
    db.execute("DELETE FROM orders WHERE user=? AND exchange=? AND unit=?", (user,
                                                                             exchange,
                                                                             unit))
    # Loop through the orders
    for order in orders:
        # Calculate how the order price is from the known good price
        order_deviation = 1.0 - (min(order['price'], price) / max(order['price'], price))
        # Using the server tolerance determine if the order is tier 1 or tier 2
        # Only tier 1 is compensated by the server
        tier = '2'
        if order_deviation <= app.config['{}.{}.{}.tolerance'.format(exchange, unit,
                                                                     order['type'])]:
            tier = '1'
        # save the order details
        db.execute("INSERT INTO orders ('user','tier','order_id','order_amount',"
                   "'order_type','exchange','unit') VALUES (?,?,?,?,?,?,?)",
                   (user, tier, str(order['id']), float(order['amount']),
                    str(order['type']), exchange, unit))
    return {'success': True, 'message': 'orders saved for validation'}


@app.get('/status')
def status(db):
    """
    Display the overall pool status
    :param db:
    :return:
    """


def build_order_list():
    """
    This is a testing method which builds a ficticious order dictionary for each
    submission to 'liquidity'
    :return:
    """
    """
    :return:
    """
    orders = []
    for x in xrange(30):
        orders.append({'price': (1234 + random.randint(-5, 5)),
                       'id': x,
                       'amount': random.randint(1, 20),
                       'type': 'bid' if int(x) % 2 == 0 else 'ask'})
    return orders


def get_price():
    """
    Set the server price primarily from the NuBot streaming server but falling back to
    feeds if that fails
    :return:
    """
    """
    :return:
    """
    return 1234

"""
Handle common errors with nice json response
"""


@app.error(code=500)
def error500(error):
    return json.dumps({'success': False, 'message': '500 error'})


@app.error(code=502)
def error502(error):
    return json.dumps({'success': False, 'message': '502 error'})


@app.error(code=503)
def error503(error):
    return json.dumps({'success': False, 'message': '503 error'})


@app.error(code=404)
def error404(error):
    return json.dumps({'success': False, 'message': '{} not found'.format(request.url)})


Timer(60.0, credit, kwargs={'app': app, 'rpc': rpc}).start()  # 60 seconds / 1 minute
Timer(86400.0, pay, kwargs={'rpc': rpc}).start()  # 86400 seconds / 24 hours
run(app, host='localhost', port=3333, debug=True)
