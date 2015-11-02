import json
import logging
import os
from threading import Timer, enumerate
from datetime import datetime
from requestlogger import WSGILogger, ApacheFormatter
from logging.handlers import TimedRotatingFileHandler
import bottle
from bottle_sqlite import SQLitePlugin
from bottle import run, request
from bitcoinrpc.authproxy import AuthServiceProxy
import time
import credit
import payout
import database
import load_config
from utils import AddressCheck
from exchanges import Bittrex, BTER, CCEDK, Poloniex, TestExchange

__author__ = 'sammoth'

app = bottle.Bottle()
bottle.debug(True)

# Create the log directory
if not os.path.isdir('logs'):
    os.mkdir('logs')

# Set the WSGI Logger facility
log_time = int(time.time())
handlers = [TimedRotatingFileHandler('logs/server-{}.log'.format(log_time),
                                     when='midnight'), ]
server = WSGILogger(app, handlers, ApacheFormatter())

# Build the application Logger
log = logging.Logger('ALP')
rotating_file = TimedRotatingFileHandler('logs/alp-{}.log'.format(log_time),
                                         when='midnight')
stream = logging.StreamHandler()
formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s',
                              datefmt='%y-%m-%d %H:%M:%S')
stream.setFormatter(formatter)
rotating_file.setFormatter(formatter)
log.addHandler(rotating_file)
log.addHandler(stream)

# Create the database if one doesn't exist
database.build(log)

# Install the SQLite plugin
app.install(SQLitePlugin(dbfile='pool.db', keyword='db'))

# Create the Exchange wrapper objects
wrappers = {'bittrex': Bittrex(),
            'bter': BTER(),
            'ccedk': CCEDK(),
            'poloniex': Poloniex(),
            'test_exchange': TestExchange()}

log.info('load pool config')
app.config.load_config('pool_config')

log.info('load exchange config')
load_config.load(app, 'exchange_config')

log.info('set up a json-rpc connection with nud')
rpc = AuthServiceProxy("http://{}:{}@{}:{}".format(app.config['rpc.user'],
                                                   app.config['rpc.pass'],
                                                   app.config['rpc.host'],
                                                   app.config['rpc.port']))


def run_credit_timer():
    log.info('running credit timer')
    credit_timer = Timer(60.0, credit.credit,
                         kwargs={'app': app, 'rpc': rpc, 'log': log})
    credit_timer.name = 'credit_timer'
    credit_timer.daemon = True
    credit_timer.start()


def run_payout_timer():
    log.info('running payout timer')
    payout_timer = Timer(86400.0, payout.pay,
                         kwargs={'rpc': rpc, 'log': log})
    payout_timer.name = 'payout_timer'
    payout_timer.daemon = True
    payout_timer.start()


if os.getenv('RUN_TIMERS', '0') == '1':
    # Set the timer for credits
    run_credit_timer()
    # Set the timer for payouts
    run_payout_timer()


def check_headers(headers):
    """
    Ensure the correct headers get passed in the request
    :param headers:
    :return:
    """
    if headers.get('Content-Type') != 'application/json':
        log.warn('invalid header - need app/json')
        return False
    return True


@app.get('/')
def root():
    """
    Show a default page with info about the server health
    :return:
    """
    return {'success': True, 'message': 'ALP Server is operational'}


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
    log.info('/register')
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
    except AttributeError:
        log.warn('no json found in request')
        return {'success': False, 'message': 'no json found in request'}
    # check for missing parameters
    if not user:
        log.warn('no user provided')
        return {'success': False, 'message': 'no user provided'}
    if not address:
        log.warn('no address provided')
        return {'success': False, 'message': 'no address provided'}
    if not exchange:
        log.warn('no exchange provided')
        return {'success': False, 'message': 'no exchange provided'}
    if not unit:
        log.warn('no unit provided')
        return {'success': False, 'message': 'no unit provided'}
    # Check for a valid address
    if address[0] != 'B':
        log.warn('%s is not a valid NBT address. No \'B\'', address)
        return {'success': False, 'message': '{} is not a valid NBT address. It '
                                             'should start with a \'B\''.format(address)}
    address_check = AddressCheck()
    if not address_check.check_checksum(address):
        log.warn('%s is not a valid NBT address. Bad checksum', address)
        return {'success': False, 'message': '{} is not a valid NBT address. The '
                                             'checksum doesn\'t match'.format(address)}
    # Check that the requests exchange is supported by the server
    if exchange not in app.config['exchanges']:
        log.warn('%s is not supported', exchange)
        return {'success': False, 'message': '{} is not supported'.format(exchange)}
    # Check that the unit is supported on the server
    if unit not in app.config['{}.units'.format(exchange)]:
        log.warn('%s is not supported on %s', unit, exchange)
        return {'success': False, 'message': '{} is not supported on {}'.format(unit,
                                                                                exchange)}
    # Check if the user already exists in the database
    check = db.execute("SELECT id FROM users WHERE user=? AND address=? AND "
                       "exchange=? AND unit=?;", (user, address, exchange,
                                                  unit)).fetchone()
    if check:
        log.warn('user is already registered')
        return {'success': False, 'message': 'user is already registered'}
    db.execute("INSERT INTO users ('user','address','exchange','unit') VALUES (?,?,?,?)",
               (user, address, exchange, unit))
    log.info('user %s successfully registered', user)
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
    log.info('/liquidity')
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
    except AttributeError:
        log.warn('no json found in request')
        return {'success': False, 'message': 'no json found in request'}
    if not user:
        log.warn('no user provided')
        return {'success': False, 'message': 'no user provided'}
    if not sign:
        log.warn('no sign provided')
        return {'success': False, 'message': 'no sign provided'}
    if not exchange:
        log.warn('no exchange provided')
        return {'success': False, 'message': 'no exchange provided'}
    if not unit:
        log.warn('no unit provided')
        return {'success': False, 'message': 'no unit provided'}
    if not req:
        log.warn('no req provided')
        return {'success': False, 'message': 'no req provided'}
    # use the submitted data to request the users orders
    orders = wrappers[exchange].validate_request(user, unit, req, sign)
    price = get_price()
    # clear existing orders for the user
    log.info('clear existing orders for user %s', user)
    db.execute("DELETE FROM orders WHERE user=? AND exchange=? AND unit=?", (user,
                                                                             exchange,
                                                                             unit))
    # Loop through the orders
    for order in orders:
        # Calculate how the order price is from the known good price
        order_deviation = 1.0 - (min(order['price'], price) / max(order['price'], price))
        # Using the server tolerance determine if the order is tier 1 or tier 2
        # Only tier 1 is compensated by the server
        tier = 'tier_2'
        if order_deviation <= app.config['{}.{}.{}.tolerance'.format(exchange, unit,
                                                                     order['type'])]:
            tier = 'tier_1'
        # save the order details
        db.execute("INSERT INTO orders ('user','tier','order_id','order_amount',"
                   "'order_type','exchange','unit') VALUES (?,?,?,?,?,?,?)",
                   (user, tier, str(order['id']), float(order['amount']),
                    str(order['type']), exchange, unit))
    log.info('user %s orders saved for validation', user)
    return {'success': True, 'message': 'orders saved for validation'}


@app.get('/exchanges')
def exchanges():
    """
    Show the app.config as it pertains to the supported exchanges
    :return:
    """
    log.info('/exchanges')
    data = {}
    for exchange in app.config['exchanges']:
        if exchange not in data:
            data[exchange] = {}
        for unit in app.config['{}.units'.format(exchange)]:
            data[exchange][unit] = {'ask': {'tolerance': app.config['{}.{}.ask.'
                                                                    'tolerance'
                                                                    ''.format(exchange,
                                                                              unit)],
                                            'tier_1': {
                                                'reward': app.config['{}.{}.ask.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'tier_1')]
                                                },
                                            'tier_2': {
                                                'reward': app.config['{}.{}.ask.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'tier_2')]
                                                }
                                            },


                                    'bid': {'tolerance': app.config['{}.{}.bid.'
                                                                    'tolerance'
                                                                    ''.format(exchange,
                                                                              unit)],
                                            'tier_1': {
                                                'reward': app.config['{}.{}.bid.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'tier_1')]
                                                },
                                            'tier_2': {
                                                'reward': app.config['{}.{}.bid.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'tier_2')]
                                                }
                                            }
                                    }
    return data


@app.get('/status')
def status(db):
    """
    Display the overall pool status.
    This will be the number of users and the amount of liquidity for each tier, side,
    unit, exchange for the last full round and the current round
    :param db:
    :return:

    We want to display

    * Total liquidity provided by pool
    * Total tier_1 by pool
    * Total tier_2 by pool
    * total liquidity by exchange
    * total tier_1 by exchange
    * total tier_2 by exchange
    * total liquidity by exchange/pair
    * total tier_1 by exchange/pair
    * total tier_2 by exchange/pair
    * total liquidity by exchange/pair/side
    * total tier_1 by exchange/pair/side
    * total tier_2 by exchange/pair/side

    * number of users
    * number of active users

    * amount 1 NBT will be rewarded currently

    """
    log.info('/status')

    # get the last credit time
    last_credit_time = db.execute("SELECT value FROM info WHERE key=?",
                                  ('last_credit_time',)).fetchone()

    # build the blank data object
    data = {'last_credit_time': last_credit_time,
            'total_liquidity': 0.0,
            'total_liquidity_bid': 0.0,
            'total_liquidity_ask': 0.0,
            'total_liquidity_tier_1': 0.0,
            'total_liquidity_tier_1_bid': 0.0,
            'total_liquidity_tier_1_ask': 0.0,
            'total_liquidity_tier_2': 0.0,
            'total_liquidity_tier_2_bid': 0.0,
            'total_liquidity_tier_2_ask': 0.0}

    # get the latest credit data from the credits field
    credit_data = db.execute("SELECT * FROM credits WHERE time=?",
                             last_credit_time).fetchall()
    log.debug(credit_data)
    # parse the data
    # id INTEGER PRIMARY KEY, time NUMBER, user TEXT, exchange TEXT, unit TEXT,
    # tier TEXT, side TEXT, provided NUMBER, total NUMBER, percentage NUMBER,
    # reward NUMBER, paid INTEGER
    for cred in credit_data:
        # increment the total liquidity (this is total over entire pool)
        data['total_liquidity'] += cred[7]
        # increment buy and sell side totals
        if cred[6] == 'bid':
            data['total_liquidity_bid'] += cred[7]
        else:
            data['total_liquidity_ask'] += cred[7]
        # increment tier_1 totals
        if cred[5] == 'tier_1':
            data['total_liquidity_tier_1'] += cred[7]
            if cred[6] == 'bid':
                data['total_liquidity_tier_1_bid'] += cred[7]
            else:
                data['total_liquidity_tier_1_bid'] += cred[7]
        # increment tier_2 totals
        if cred[5] == 'tier_2':
            data['total_liquidity_tier_2'] += cred[7]
            if cred[6] == 'bid':
                data['total_liquidity_tier_2_bid'] += cred[7]
            else:
                data['total_liquidity_tier_2_ask'] += cred[7]

    return {'status': True, 'message': data}


def get_price():
    """
    Set the server price primarily from the NuBot streaming server but falling back to
    feeds if that fails
    :return:
    """
    return 1234


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
    return json.dumps({'success': False, 'message': '404 {} not found'
                                                    ''.format(request.url)})


@app.error(code=405)
def error405(error):
    return json.dumps({'success': False, 'message': '405 error. '
                                                    'Incorrect HTTP method used'})


if __name__ == '__main__':
    # Run the server
    run(server, host='localhost', port=int(os.environ.get("PORT", 3333)), debug=True)
