import json
import logging
import os
from threading import Timer
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
    address_check = AddressCheck()
    if address[0] != 'B' and not address_check.check_checksum(address):
        log.warn('%s is not a valid NBT address', address)
        return {'success': False, 'message': '{} is not a valid NBT address'.format(
            address)}
    # Check that the requests exchange is supported by the server
    if exchange not in app.config['exchanges']:
        log.warn('{} is not supported'.format(exchange))
        return {'success': False, 'message': '{} is not supported'.format(exchange)}
    # Check that the unit is supported on the server
    if unit not in app.config['{}.units'.format(exchange)]:
        log.warn('{} is not supported on {}'.format(unit, exchange))
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
    log.info('user {} successfully registered'.format(user))
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
    log.info('clear existing orders for user {}'.format(user))
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
    log.info('user {} orders saved for validation'.format(user))
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
            data[exchange][unit] = {'ask': {'tolerance':
                                            app.config['{}.{}.ask.tolerance'.format(
                                                       exchange, unit)],
                                            'reward':
                                            app.config['{}.{}.ask.reward'.format(
                                                       exchange, unit)]},
                                    'bid': {'tolerance':
                                            app.config['{}.{}.bid.tolerance'.format(
                                                       exchange, unit)],
                                            'reward':
                                            app.config['{}.{}.bid.reward'.format(
                                                       exchange, unit)]}}
    return data


@app.get('/status')
def status(db):
    """
    Display the overall pool status.
    This will be the number of users and the amount of liquidity for each tier, side,
    unit, exchange for the last full round and the current round
    :param db:
    :return:
    """
    log.info('/status')
    # build the data dict
    data = {}
    # get the last credit round
    credit_data = db.execute("SELECT * FROM credits WHERE time=(SELECT time FROM "
                             "credits ORDER BY time DESC LIMIT 1)").fetchall()
    for cred in credit_data:
        if 'total_tier_1' in data and 'total_tier_2' in data:
            break
        if 'last_credit_time' not in data:
            data['last_credit_time'] = cred[1]
        if 'total_tier_1' not in data and cred[5] == 'tier_1':
            data['total_tier_1'] = cred[8]
        if 'total_tier_2' not in data and cred[5] == 'tier_2':
            data['total_tier_2'] = cred[8]

    data['total'] = data['total_tier_1'] + data['total_tier_2']

    return {'success': True, 'message': data}


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
    return json.dumps({'success': False, 'message': '404 {} not found'.format(
        request.url)})


if __name__ == '__main__':

    log.info('load pool config')
    app.config.load_config('pool_config')

    log.info('load exchange config')
    load_config.load(app, 'exchange_config')

    log.info('set up a json-rpc connection with nud')
    rpc = AuthServiceProxy("http://{}:{}@{}:{}".format(app.config['rpc.user'],
                                                       app.config['rpc.pass'],
                                                       app.config['rpc.host'],
                                                       app.config['rpc.port']))
    # Set the timer for credits
    Timer(60.0, credit.credit, kwargs={'app': app, 'rpc': rpc, 'log': log}).start()
    # Set the timer for payouts
    Timer(86400.0, payout.pay, kwargs={'rpc': rpc, 'log': log}).start()
    # Run the server
    run(server, host='localhost', port=int(os.environ.get("PORT", 3333)), debug=True)
