import json
import logging
import os
from threading import Timer
from requestlogger import WSGILogger, ApacheFormatter
from logging.handlers import TimedRotatingFileHandler
import bottle
from bottle_sqlite import SQLitePlugin
import bottle_pgsql
from bottle import run, request, response
from bitcoinrpc.authproxy import AuthServiceProxy
import time
import credit
import payout
import database
import load_config
from price_fetcher import PriceFetcher
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

# Install the Database plugin based on the environment
if os.getenv('DATABASE', '') == 'POSTGRES':
    app.install(bottle_pgsql.Plugin('dbname={} user={} password={}'.format(
        app.config['db.name'], app.config['db.user'], app.config['db.pass'])))
else:
    app.install(SQLitePlugin(dbfile='pool.db', keyword='db'))

# Create the Exchange wrapper objects
wrappers = {'bittrex': Bittrex(),
            'bter': BTER(),
            'ccedk': CCEDK(),
            'poloniex': Poloniex(),
            'test_exchange': TestExchange(),
            'test_exchange_2': TestExchange()}

# Load the configs
log.info('load pool config')
app.config.load_config('pool_config')

log.info('load exchange config')
load_config.load(app, 'exchange_config')

# Set up a connection with nud
log.info('set up a json-rpc connection with nud')
rpc = AuthServiceProxy("http://{}:{}@{}:{}".format(app.config['rpc.user'],
                                                   app.config['rpc.pass'],
                                                   app.config['rpc.host'],
                                                   app.config['rpc.port']))


# set up a price fetcher for each currency
pf = {}
for unit in app.config['units']:
    pf[unit] = PriceFetcher(unit, log)
    # price streamer doesn't handle usd, we can hard code the price here
    if unit == 'usd':
        pf[unit].price = 1.00
        log.info('usd price set to 1.00')
        continue
    # otherwise subscribe to the price feed
    pf[unit].subscribe()


def run_credit_timer():
    """
    This method allows the credit timer to be run from test server and from wsgi
    :return:
    """
    log.info('running credit timer')
    credit_timer = Timer(60.0, credit.credit,
                         kwargs={'app': app, 'rpc': rpc, 'log': log})
    credit_timer.name = 'credit_timer'
    credit_timer.daemon = True
    credit_timer.start()


def run_payout_timer():
    """
    This method allows the payout timer to be run from test server and from wsgi
    :return:
    """
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
    # get the price fetchers
    pf = set_price_fetchers()


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
    except (AttributeError, ValueError):
        log.warn('request body must be valid json')
        return {'success': False, 'message': 'request body must be valid json'}
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
    except (AttributeError, ValueError):
        log.warn('request body must be valid json')
        return {'success': False, 'message': 'request body must be valid json'}
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
    if exchange not in app.config['exchanges']:
        log.warn('invalid exchange')
        return {'success': False, 'message': '{} is not supported'.format(exchange)}
    if unit not in app.config['{}.units'.format(exchange)]:
        log.warn('invalid unit')
        return {'success': False, 'message': '{} is not supported on {}'.format(unit,
                                                                                exchange)}
    # use the submitted data to request the users orders
    orders = wrappers[exchange].validate_request(user, unit, req, sign)
    price = pf[unit].price
    if price is None:
        log.error('unable to fetch current price for %s' % unit)
        return {'success': False, 'message': 'unable to fetch current price for {}'.
                format(unit)}
    # clear existing orders for the user
    log.info('clear existing orders for user %s', user)
    db.execute("DELETE FROM orders WHERE user=? AND exchange=? AND unit=?", (user,
                                                                             exchange,
                                                                             unit))
    # Loop through the orders
    for order in orders:
        # Calculate how the order price is from the known good price
        order_deviation = 1.0 - (min(order['price'], price) / max(order['price'], price))
        # Using the server tolerance determine if the order is rank 1 or rank 2
        # Only rank 1 is compensated by the server
        rank = 'rank_2'
        if order_deviation <= app.config['{}.{}.{}.tolerance'.format(exchange, unit,
                                                                     order['type'])]:
            rank = 'rank_1'
        # save the order details
        db.execute("INSERT INTO orders ('user','rank','order_id','order_amount',"
                   "'side','exchange','unit','credited') VALUES (?,?,?,?,?,?,?,?)",
                   (user, rank, str(order['id']), float(order['amount']),
                    str(order['type']), exchange, unit, 0))
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
                                            'rank_1': {
                                                'reward': app.config['{}.{}.ask.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'rank_1')]
                                                },
                                            'rank_2': {
                                                'reward': app.config['{}.{}.ask.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'rank_2')]
                                                }
                                            },


                                    'bid': {'tolerance': app.config['{}.{}.bid.'
                                                                    'tolerance'
                                                                    ''.format(exchange,
                                                                              unit)],
                                            'rank_1': {
                                                'reward': app.config['{}.{}.bid.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'rank_1')]
                                                },
                                            'rank_2': {
                                                'reward': app.config['{}.{}.bid.{}'
                                                                     '.reward'
                                                                     ''.format(exchange,
                                                                               unit,
                                                                               'rank_2')]
                                                }
                                            }
                                    }
    return data


@app.get('/status')
def status(db):
    """
    Display the overall pool status.
    This will be the number of users and the amount of liquidity for each rank, side,
    unit, exchange for the last full round and the current round
    :param db:
    :return:
    """
    log.info('/status')
    # get the prices
    prices = {}
    for unit in app.config['units']:
        prices[unit] = pf[unit].price
    # get the latest stats from the database
    stats_data = db.execute("SELECT * FROM stats ORDER BY id DESC LIMIT 1").fetchone()
    if not stats_data:
        return {'status': False, 'message': 'no statistics exist yet.'}
    response.set_header('Content-Type', 'application/json')
    return json.dumps({'status': True, 'message': {'collected': stats_data[1],
                                                   'meta': json.loads(stats_data[2]),
                                                   'totals': json.loads(stats_data[3]),
                                                   'rewards': json.loads(stats_data[4]),
                                                   'prices': prices}},
                      sort_keys=True)


@app.get('/<user>/orders')
def user_orders(db, user):
    """
    Get the users order history
    :param db:
    :return:
    """
    orders = db.execute("SELECT id,order_id,exchange,unit,side,rank,order_amount,"
                        "credited FROM orders WHERE user=? ORDER BY id DESC LIMIT 100",
                        (user,)).fetchall()
    # build a list for the order output
    output_orders = []
    # parse the orders
    for order in orders:
        # build the order into a dict
        output_order = {'order_id': order[1], 'exchange': order[2], 'unit': order[3],
                        'side': order[4], 'rank': order[5], 'amount': order[6],
                        'credited': order[7]}
        # get credit detail if the order has been credited
        if order[7] == 1:
            cred = db.execute("SELECT time,total,percentage,reward FROM credits WHERE "
                              "order_id=?", (order[0],)).fetchone()
            output_order['credited_time'] = cred[0]
            output_order['total_liquidity'] = round(cred[1], 8)
            output_order['percentage'] = round(cred[2], 8)
            output_order['reward'] = round(cred[3], 8)
        output_orders.append(output_order)
    return {'success': True, 'message': output_orders}


@app.get('/<user>/stats')
def user_credits(db, user):
    """
    Get the users current stats
    :param db:
    :return:

    We want:

    total reward
    reward last round
    total liquidity provided last round
    percentage provided last round

    """
    # set the user stats to return if nothing is gathered
    user_stats = {'total_reward': 0.0,
                  'history': []}
    # get the total reward
    total = db.execute("SELECT SUM(reward) FROM credits WHERE user=?",
                       (user,)).fetchone()[0]
    if total:
        user_stats['total_reward'] = round(float(total), 8)
    # calculate the last 10 round net worth for this user
    last_rounds = db.execute("SELECT DISTINCT time FROM credits ORDER BY time DESC "
                             "LIMIT 50").fetchall()
    for round_time in last_rounds:
        worth = db.execute("SELECT SUM(provided), SUM(reward) FROM credits WHERE user=? "
                           "AND time=?", (user, round_time[0])).fetchone()
        if worth is not None:
            round_worth = {'round_time': round_time[0],
                           'provided': worth[0],
                           'reward': worth[1]}
            user_stats['history'].append(round_worth)
    return {'success': True, 'message': user_stats}


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
