from threading import Timer, Thread, enumerate
import sqlite3
import time
from bitcoinrpc.authproxy import JSONRPCException

__author__ = 'sammoth'

"""
Every thing in this module pertains to the crediting of orders.
LPCs submit their signed 'open_orders' query through the 'liquidity' server end point.
The server validates each order and determines if they are tier 1 or 2 using the price
at that moment.
The credit function runs each minute and gathers the submitted orders from the database
For each user it calculates what percentage of the total submitted liquidity they have
provided and gives them a 'credit' in the database.
It also uses that data to submit liquidity info back to Nu
"""


def credit(app, rpc, log, start_timer=True):
    """
    This runs every minute and calculates the total liquidity on order (tier 1) and
    each users proportion of it
    :return:
    """
    # Set the timer going again (use the boolean to allow testing)
    if start_timer:
        credit_timer = Timer(60.0, credit,
                             kwargs={'app': app, 'rpc': rpc, 'log': log})
        credit_timer.name = 'credit_timer'
        credit_timer.daemon = True
        credit_timer.start()
    log.info('Starting Credit')
    conn = sqlite3.connect('pool.db')
    db = conn.cursor()
    # Get all the orders from the database.
    # We delete them as soon as we've got them to allow users to begin submitting again
    all_orders = db.execute("SELECT * FROM orders").fetchall()
    db.execute('DELETE FROM orders')
    conn.commit()
    conn.close()
    # get the total amount of liquidity for tier 1 and 2
    total = {'tier_1': get_total_liquidity(app, all_orders, 'tier_1'),
             'tier_2': get_total_liquidity(app, all_orders, 'tier_2')}

    # We've calculated the totals so submit them as liquidity_info
    Thread(target=liquidity_info, kwargs={'rpc': rpc, 'tier_1': total['tier_1'],
                                          'tier_2': total['tier_2'], 'log': log})

    # build the orders into a dictionary of lists based on the user api key
    user_orders = {}
    for order in all_orders:
        if order[1] not in user_orders:
            user_orders[order[1]] = []
        user_orders[order[1]].append(order)

    # set up a list of credited orders to avoid duplicate orders being credited
    credited_orders = []
    for user in user_orders:
        # for each user get all the orders
        orders = user_orders[user]
        # build a dictionary to hold the tier liquidity amounts
        provided_liquidity = {'tier_1': {}, 'tier_2': {}}
        for tier in provided_liquidity:
            for exchange in app.config['exchanges']:
                provided_liquidity[tier][exchange] = {}
                for unit in app.config['{}.units'.format(exchange)]:
                    provided_liquidity[tier][exchange][unit] = {}
                    for side in ['ask', 'bid']:
                        provided_liquidity[tier][exchange][unit][side] = 0.00
        # parse the orders
        for order in orders:
            # Hash the order on order id, amount, side, exchange and unit to avoid
            # duplication
            order_hash = '{}.{}.{}.{}.{}'.format(order[3], order[4], order[5],
                                                 order[6], order[7])
            # check here to see if the order has already been credited
            if order_hash in credited_orders:
                continue
            # add the order to the list
            credited_orders.append(order_hash)

            # add the order amount to the liquidity provided
            provided_liquidity[order[2]][order[6]][order[7]][order[5]] += float(order[4])

        # Calculate the percentage of the tier 1 liquidity that this user provides
        # for each exchange/unit combination
        calculate_rewards(app, 'tier_1', provided_liquidity, total['tier_1'], user)

        # Record for tier 2 orders also to allow for user reports
        # There is no reward for tier 2
        calculate_rewards(app, 'tier_2', provided_liquidity, total['tier_2'], user)
    log.info('Credit finished')
    return


def get_total_liquidity(app, orders, tier):
    """
    Given a list of orders from the database, calculate the total amount of liquidity
    for the given tier
    :param orders:
    :param tier:
    :return:
    """
    # build the liquidity object
    liquidity = {}
    for exchange in app.config['exchanges']:
        if exchange not in liquidity:
            liquidity[exchange] = {}
        for unit in app.config['{}.units'.format(exchange)]:
            if unit not in liquidity[exchange]:
                liquidity[exchange][unit] = {}
            for side in ['ask', 'bid']:
                liquidity[exchange][unit][side] = 0.00
    # parse the orders and update the liquidity object accordingly
    for order in orders:
        # only add orders for the current tier
        if order[2] != tier:
            continue
        # get the order details
        exchange = order[6]
        unit = order[7]
        side = order[5]
        liquidity[exchange][unit][side] += float(order[4])
    return liquidity


def calculate_rewards(app, tier, provided_liquidity, total, user):
    """
    Calculate the rewards for
    :param tier:
    :return:
    """
    credit_time = int(time.time())
    # add one blank line to database to show that credit occurred
    conn = sqlite3.connect('pool.db')
    db = conn.cursor()
    db.execute("UPDATE info set value=? WHERE key=?", (credit_time, 'last_credit_time'))
    conn.commit()
    conn.close()
    for exchange in provided_liquidity[tier]:
        for unit in provided_liquidity[tier][exchange]:
            for side in provided_liquidity[tier][exchange][unit]:
                provided = float(provided_liquidity[tier][exchange][unit][side])
                if provided <= 0.00:
                    continue
                total_l = float(total[exchange][unit][side])
                if total_l <= 0.00:
                    continue
                percentage = (provided / total_l) if total_l > 0.00 else 0.00
                # Use the percentage to calculate the reward for this round
                reward = percentage * app.config['{}.{}.{}.{}'
                                                 '.reward'.format(exchange,
                                                                  unit,
                                                                  side,
                                                                  tier)]
                # save the details to the database
                # set the connection here to keep it open as short as possible
                conn = sqlite3.connect('pool.db')
                db = conn.cursor()
                db.execute("INSERT INTO credits (time,user,exchange,unit,tier,side,"
                           "provided,total,percentage,reward,paid) VALUES  "
                           "(?,?,?,?,?,?,?,?,?,?,?)",
                           (credit_time, user, exchange, unit, tier, side, provided,
                            total_l, (percentage * 100), reward, 0))
                conn.commit()
                conn.close()
    return


def liquidity_info(app, rpc, tier_1, tier_2, log):
    """
    Calculate the current amount of liquidity in tiers 1 and 2 and submit them to Nu
    :return:
    """
    for exchange in tier_1:
        for unit in tier_1[exchange]:
            identifier = "1:{}:{}:{}".format('NBT{}'.format(unit.upper()),
                                             exchange,
                                             app.config['pool.name'])
            try:
                rpc.liquidityinfo('B', tier_1[exchange][unit]['bid'],
                                  tier_1[exchange][unit]['ask'],
                                  app.config['pool.grant_address'], identifier)
            except JSONRPCException as e:
                log.error('Sending tier 1 liquidity info failed: {}'.format(e.message))

    for exchange in tier_2:
        for unit in tier_2[exchange]:
            identifier = "2:{}:{}:{}".format('NBT{}'.format(unit.upper()),
                                             exchange,
                                             app.config['pool.name'])
            try:
                rpc.liquidityinfo('B', tier_2[exchange][unit]['bid'],
                                  tier_2[exchange][unit]['ask'],
                                  app.config['pool.grant_address'], identifier)
            except JSONRPCException as e:
                log.error('Sending tier 2 liquidity info failed: {}'.format(e.message))
