from threading import Timer, Thread
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


def credit(app, rpc):
    """
    This runs every minute and calculates the total liquidity on order (tier 1) and
    each users proportion of it
    :return:
    """
    # Set the timer going again
    Timer(60.0, credit).start()
    print 'Starting Credit'
    conn = sqlite3.connect('pool.db')
    db = conn.cursor()
    # Get all the orders from the database.
    # We delete them as soon as we've got them to allow users to begin submitting again
    all_orders = db.execute("SELECT * FROM orders").fetchall()
    db.execute('DELETE FROM orders')
    conn.commit()
    conn.close()
    # Get the total for tier 1 liquidity for each exchange/unit combination
    total_tier_1 = get_total_liquidity(app, all_orders, '1')
    # Get the total for tier 2 liquidity also
    total_tier_2 = get_total_liquidity(app, all_orders, '2')

    # We've calculated the totals so submit them as liquidity_info
    Thread(target=liquidity_info, kwargs={'rpc': rpc, 'tier_1': total_tier_1,
                                          'tier_2': total_tier_2})

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
        # This will end up being a multi dimensioned dictionary
        # Each tier can contain exchanges which in turn contain units. These are the
        # keys used for the total liquidity and allow us to set different tolerances
        # and rewards for different pairs on different exchanges
        tiers = {'1': {}, '2': {}}
        for order in orders:
            # Hash the order on order id, amount, type exchange and unit to avoid
            # duplication
            order_hash = '{}.{}.{}.{}.{}'.format(order[3], order[4], order[5],
                                                 order[6], order[7])
            # check here to see if the order has already been credited
            if order_hash in credited_orders:
                continue
            # add the order to the list
            credited_orders.append(order_hash)
            # these variables makes it easier to see what's going on
            tier = order[2]
            order_amount = order[4]
            side = order[5]
            exchange = order[6]
            unit = order[7]
            # check that we are recording liquidity for the current exchange
            if exchange not in tiers[tier]:
                tiers[tier][exchange] = {}
            # do the same for the current unit
            if unit not in tiers[tier][exchange]:
                tiers[tier][exchange][unit] = {}
            # and again for the side
            if side not in tiers[tier][exchange][unit]:
                tiers[tier][exchange][unit][side] = 0.0
            # add the order amount to the liquidity for this exchange/unit/side
            tiers[tier][exchange][unit][side] += float(order_amount)

        # Calculate the percentage of the tier 1 liquidity that this user provides
        # for each exchange/unit combination
        calculate_rewards(app, '1', tiers, total_tier_1, user)

        # Record for tier 2 orders also to allow for user reports
        # There is no reward for tier 2
        calculate_rewards(app, '2', tiers, total_tier_2, user)

    return


def get_total_liquidity(app, orders, tier):
    """
    Given a list of orders from the database, calculate the total amount of liquidity
    for the given tier
    :param orders:
    :param tier:
    :return:
    """
    liquidity = {}
    for exchange in app.config['exchanges']:
        if exchange not in liquidity:
            liquidity[exchange] = {}
        for unit in app.config['{}.units'.format(exchange)]:
            if unit not in liquidity[exchange]:
                liquidity[exchange][unit] = {}
            for side in ['ask', 'bid']:
                total = 0.00
                for order in orders:
                    # exclude based on tier
                    if order[2] != tier:
                        continue
                    # exclude orders not for this exchange/unit
                    if order[6] != exchange:
                        continue
                    if order[7] != unit:
                        continue
                    if order[5] != side:
                        continue
                    # increase the total liquidity by the amount in the order
                    total += float(order[4])
                    if side not in liquidity[exchange][unit]:
                        liquidity[exchange][unit][side] = total
    return liquidity


def calculate_rewards(app, tier, tiers, total, user):
    """
    Calculate the rewards for
    :param tier:
    :return:
    """

    for exchange in tiers[tier]:
        for unit in tiers[tier][exchange]:
            for side in tiers[tier][exchange][unit]:
                percentage = (float(tiers[tier][exchange][unit][side]) /
                              float(total[exchange][unit][side]))
                # Use the percentage to calculate the reward for this round
                if tier == '1':
                    reward = percentage * app.config['{}.{}.{}.reward'.format(exchange,
                                                                              unit,
                                                                              side)]
                else:
                    reward = 0.00 # No reward for tier 2
                # save the details to the database
                # set the connection here to keep it open as short as possible
                conn = sqlite3.connect('pool.db')
                db = conn.cursor()
                db.execute("INSERT INTO credits (time,user,exchange,unit,tier,"
                           "side,provided,total,percentage,reward,paid) VALUES  (?,?,?,"
                           "?,?,?,?,?,?,?,?)",
                           (time.time(), user, exchange, unit, tier, side,
                            tiers[tier][exchange][unit][side],
                            total[exchange][unit][side], (percentage * 100), reward, 0))
                conn.commit()
                conn.close()
    return


def liquidity_info(app, rpc, tier_1, tier_2):
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
                print 'Sending tier 1 liquidity info failed: {}'.format(e.message)

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
                print 'Sending tier 2 liquidity info failed: {}'.format(e.message)
