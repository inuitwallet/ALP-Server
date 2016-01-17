import json
import logging
import time
import urlparse
from logging.handlers import TimedRotatingFileHandler
from threading import Timer

import bottle
import bottle_pgsql
import os
from bitcoinrpc.authproxy import AuthServiceProxy
from bottle import run, request, response, static_file
from requestlogger import WSGILogger, ApacheFormatter
from src import credit, database, payout, config
import src.exchanges
from src.price_fetcher import PriceFetcher
from src.utils import AddressCheck

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

# Load the config
config.load(app, log, log_output=True)

# Install the Postgres plugin
if os.getenv("DATABASE_URL", None) is not None:
    urlparse.uses_netloc.append("postgres")
    url = urlparse.urlparse(os.environ["DATABASE_URL"])
    app.install(bottle_pgsql.Plugin('dbname={} user={} password={} '
                                    'host={} port={}'.format(url.path[1:],
                                                             url.username,
                                                             url.password,
                                                             url.hostname,
                                                             url.port)))
else:
    app.install(bottle_pgsql.Plugin('dbname={} user={} password={} '
                                    'host={} port={}'.format(app.config['db.name'],
                                                             app.config['db.user'],
                                                             app.config['db.pass'],
                                                             app.config['db.host'],
                                                             app.config['db.port'])))

# Create the database if one doesn't exist
database.build(app, log)

# Create the Exchange wrapper objects
wrappers = {}
if 'bittrex' in app.config['exchanges']:
    wrappers['bittrex'] = src.exchanges.Bittrex()
if 'bter' in app.config['exchanges']:
    wrappers['bter'] = src.exchanges.BTER()
if 'ccedk' in app.config['exchanges']:
    wrappers['ccedk'] = src.exchanges.CCEDK()
if 'poloniex' in app.config['exchanges']:
    wrappers['poloniex'] = src.exchanges.Poloniex()
if 'test_exchange' in app.config['exchanges']:
    wrappers['test_exchange'] = src.exchanges.TestExchange()
if 'test_exchange_2' in app.config['exchanges']:
    wrappers['test_exchange_2'] = src.exchanges.TestExchange()

# save the start time of the server for reporting up-time
app.config['start_time'] = time.time()

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

# Set the timer for credits
log.info('running credit timer')
credit_timer = Timer(60.0, credit.credit,
                     kwargs={'app': app, 'rpc': rpc, 'log': log})
credit_timer.name = 'credit_timer'
credit_timer.daemon = True
credit_timer.start()

# Set the timer for payouts
log.info('running payout timer')
conn = database.get_db(app)
db = conn.cursor()
db.execute("SELECT value FROM info WHERE key = %s", ('next_payout_time',))
next_payout_time = int(db.fetchone()[0])
if next_payout_time == 0:
    payout_time = 86400
    db.execute('UPDATE info SET value=%s WHERE key=%s', (int(time.time() + payout_time),
                                                         'next_payout_time'))
else:
    payout_time = int(next_payout_time - int(time.time()))
conn.commit()
conn.close()
payout_timer = Timer(payout_time, payout.pay,
                     kwargs={'app': app, 'rpc': rpc, 'log': log})
payout_timer.name = 'payout_timer'
payout_timer.daemon = True
payout_timer.start()


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


@app.get('/favicon.ico')
def get_favicon():
    return static_file('favicon.ico', root='static')


@app.post('/register')
def register(db):
    """
    Register a new user on the server
    Requires:
        user - API public Key
        address - Valid NBT payout address
        exchange - supported exchange
        unit - supported currency
    :param db:
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
    db.execute("SELECT id FROM users WHERE key=%s AND address=%s AND exchange=%s "
               "AND unit=%s;", (user, address, exchange, unit))
    check = db.fetchone()
    if check:
        log.warn('user is already registered')
        return {'success': False, 'message': 'user is already registered'}
    db.execute("INSERT INTO users (key,address,exchange,unit) VALUES (%s,%s,%s,"
               "%s)", (user, address, exchange, unit))
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
    :param db:
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
    # check that the user is registered
    db.execute("SELECT id FROM users WHERE key=%s", (user,))
    user_check = db.fetchone()
    if user_check is None:
        log.error('user %s is not registered', user)
        return {'success': False, 'message': 'user {} is not registered'.format(user)}
    # use the submitted data to request the users orders
    valid = wrappers[exchange].validate_request(user=user, unit=unit, req=req, sign=sign)
    if valid['message'] != 'success':
        log.error('%s: %s', exchange, valid['message'])
        return {'success': valid['success'], 'message': valid['message']}
    orders = valid['orders']
    # get the price from the price feed
    price = pf[unit].price
    if price is None:
        log.error('unable to fetch current price for %s', unit)
        return {'success': False, 'message': 'unable to fetch current price for {}'.
                format(unit)}
    # clear existing orders for the user
    db.execute("DELETE FROM orders WHERE key=%s AND exchange=%s AND unit=%s", (user,
                                                                               exchange,
                                                                               unit))
    # Loop through the orders
    for order in orders:
        # Calculate how the order price is from the known good price
        order_deviation = 1.00 - (min(float(order['price']), float(price)) /
                                  max(float(order['price']), float(price)))
        # Use the rank tolerances to determine the rank of the order
        order_rank = ''
        # first build a sorted list of tolerances
        tolerances = []
        for rank in app.config['{}.{}.{}.ranks'.format(exchange, unit, order['side'])]:
            try:
                tolerance = app.config['{}.{}.{}.{}.tolerance'.format(
                        exchange, unit, order['side'], rank)]
            except KeyError:
                tolerance = 1.00
            tolerances.append((rank, tolerance))
        for tolerance in sorted(tolerances, key=lambda tup: tup[1]):
            if float(order_deviation) <= float(tolerance[1]):
                order_rank = tolerance[0]
                break
        # save the order details
        db.execute("INSERT INTO orders (key,rank,order_id,order_amount,side,order_price,"
                   "server_price,exchange,unit,deviation,tolerance,credited) VALUES "
                   "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                   (user, order_rank, str(order['id']), float(order['amount']),
                    str(order['side']), float(order['price']), float(price), exchange,
                    unit, float(order_deviation), float(tolerance[1]), 0))
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
    for ex in app.config['exchanges']:
        if ex not in data:
            data[ex] = {}
        for u in app.config['{}.units'.format(ex)]:
            data[ex][u] = {
                'reward': app.config['{}.{}.reward'.format(ex, u)],
                'target': app.config['{}.{}.target'.format(ex, u)]
            }
            for side in ['ask', 'bid']:
                data[ex][u][side] = {'ratio': app.config['{}.{}.ask.ratio'.format(ex, u)]}
                for rank in app.config['{}.{}.{}.ranks'.format(ex, u, side)]:
                    data[ex][u][side][rank] = {
                        'ratio': app.config['{}.{}.{}.{}.ratio'.format(ex, u,
                                                                       side, rank)],
                        'tolerance': app.config['{}.{}.{}.{}.tolerance'.format(ex,
                                                                               u,
                                                                               side,
                                                                               rank)]
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
    # get the latest stats from the database using jsonb
    db.execute("SELECT * FROM stats ORDER BY id DESC LIMIT 1")
    stats_data = db.fetchone()
    if not stats_data:
        return {'status': False, 'message': 'no statistics exist yet.'}
    response.set_header('Content-Type', 'application/json')
    return json.dumps({'status': True, 'message': {'meta': stats_data['meta'],
                                                   'totals': stats_data['totals'],
                                                   'rewards': stats_data['rewards'],
                                                   'prices': prices},
                       'server_time': int(time.time()),
                       'server_up_time': int((time.time() - app.config['start_time']))},
                      sort_keys=True)


@app.get('/<user>/orders')
def user_orders(db, user):
    """
    Get the users order history
    :param db:
    :return:
    """
    # error if the user doesn't exist
    db.execute("SELECT id FROM users WHERE key=%s", (user,))
    exists = db.fetchone()
    if exists is None:
        log.error('user %s does not exist', user)
        return {'success': False, 'message': 'user {} is not registered'.format(user)}
    # fetch the users orders
    db.execute("SELECT id,order_id,exchange,unit,side,rank,order_amount,order_price,"
               "server_price,deviation,tolerance,credited FROM orders WHERE key=%s ORDER "
               "BY id DESC LIMIT 100", (user,))
    orders = db.fetchall()
    # build a list for the order output
    output_orders = []
    # parse the orders
    for order in orders:
        # get credit detail if the order has been credited
        if order['credited'] == 1:
            db.execute("SELECT time,percentage,reward FROM credits WHERE "
                       "order_id=%s", (order['id'],))
            cred = db.fetchone()
            order['credit_info'] = {'credited_time': int(cred['time']),
                                    'percentage_of_rank': round(cred['percentage'], 8),
                                    'credit_amount': round(cred['reward'], 8)}
            # get other details from the stats table
            db.execute("SELECT totals->'{ex}'->'{unit}'->'total' as unit_total, "
                       "config->'{ex}'->'{unit}'->'target' as unit_target, "
                       "config->'{ex}'->'{unit}'->'reward' as unit_reward, "
                       "config->'{ex}'->'{unit}'->'{side}'->'ratio' as side_ratio, "
                       "totals->'{ex}'->'{unit}'->'{side}'->'{rank}' as rank_total, "
                       "config->'{ex}'->'{unit}'->'{side}'->'{rank}'->'ratio' as "
                       "rank_ratio, "
                       "rewards->'{ex}'->'{unit}'->'{side}'->'{rank}' as rank_reward "
                       "FROM stats WHERE time=%s".format(ex=order['exchange'],
                                                         unit=order['unit'],
                                                         side=order['side'],
                                                         rank=order['rank']),
                       (order['credit_info']['credited_time'], ))
            stats = db.fetchone()
            order['credit_info']['unit_total_liquidity'] = stats['unit_total']
            order['credit_info']['unit_target'] = stats['unit_target']
            order['credit_info']['unit_reward'] = stats['unit_reward']
            unit_ratio = stats['unit_total'] / stats['unit_target']
            unit_ratio = 1.0 if unit_ratio >= 1.0 else unit_ratio
            order['credit_info']['calculated_unit_reward'] = stats['unit_reward'] * unit_ratio
            order['credit_info']['side_ratio'] = stats['side_ratio']
            order['credit_info']['side_reward'] = order['credit_info'][
                'calculated_unit_reward'] * stats['side_ratio']
            order['credit_info']['rank_total_liquidity'] = stats['rank_total']
            order['credit_info']['rank_reward'] = stats['rank_reward']
            order['credit_info']['rank_ratio'] = stats['rank_ratio']
        output_orders.append(order)
    return {'success': True, 'message': output_orders, 'server_time': int(time.time())}


@app.get('/<user>/stats')
def user_credits(db, user):
    """1
    Get the users current stats
    :param db:
    :return:

    We want:

    total reward
    reward last round
    total liquidity provided last round
    percentage provided last round

    """
    # error if the user doesn't exist
    db.execute("SELECT id FROM users WHERE key=%s", (user,))
    exists = db.fetchone()
    if exists is None:
        log.error('user %s does not exist', user)
        return {'success': False, 'message': 'user {} is not registered'.format(user)}
    # set the user stats to return if nothing is gathered
    user_stats = {'total_reward': 0.0,
                  'current_reward': 0.0,
                  'history': []}
    # get the total reward
    db.execute("SELECT SUM(reward) FROM credits WHERE key=%s", (user,))
    total = db.fetchone()
    if total['sum'] is not None:
        user_stats['total_reward'] = round(float(total['sum']), 8)
    # get the current reward
    db.execute("SELECT SUM(reward) FROM credits WHERE key=%s AND paid=0", (user,))
    current = db.fetchone()
    if current['sum'] is not None:
        user_stats['current_reward'] = round(float(current['sum']), 8)
    # calculate the last 10 round net worth for this user
    db.execute("SELECT DISTINCT time FROM credits ORDER BY time DESC LIMIT 50")
    last_rounds = db.fetchall()
    for round_time in last_rounds:
        db.execute("SELECT SUM(provided) AS provided, SUM(reward) AS reward FROM credits "
                   "WHERE key=%s AND "
                   "time=%s", (user, round_time['time']))
        worth = db.fetchone()
        if worth is not None:
            round_worth = {'round_time': int(round_time['time']),
                           'provided': 0.0 if worth['provided'] is None
                           else worth['provided'],
                           'reward': 0.0 if worth['reward'] is None else worth['reward']}
            user_stats['history'].append(round_worth)
    return {'success': True, 'message': user_stats, 'server_time': int(time.time())}


@app.error(code=500)
def error500(error):
    return json.dumps({'success': False, 'message': '500 error: {}'.format(error)})


@app.error(code=502)
def error502(error):
    return json.dumps({'success': False, 'message': '502 error: {}'.format(error)})


@app.error(code=503)
def error503(error):
    return json.dumps({'success': False, 'message': '503 error: {}'.format(error)})


@app.error(code=404)
def error404(error):
    return json.dumps({'success': False, 'message': '404 {} not found: {}'
                                                    ''.format(request.url, error)})


@app.error(code=405)
def error405(error):
    return json.dumps({'success': False, 'message': '405 error. '
                                                    'Incorrect HTTP method used: '
                                                    '{}'.format(error)})


if __name__ == '__main__':
    # Run the server
    run(server, host='localhost', port=int(os.environ.get("PORT", 3333)), debug=True)
