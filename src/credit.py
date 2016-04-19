import json
import time
from threading import Timer, Thread

import database
from bitcoinrpc.authproxy import JSONRPCException
from src import config
from src.utils import get_rpc

__author__ = 'sammoth'

"""
Every thing in this module pertains to the crediting of orders.
LPCs submit their signed 'open_orders' query through the 'liquidity' server end point.
The server validates each order and determines if they are rank 1 or 2 using the price
at that moment.
The credit function runs each minute and gathers the submitted orders from the database
For each user it calculates what percentage of the total submitted liquidity they have
provided and gives them a 'credit' in the database.
It also uses that data to submit liquidity info back to Nu
"""


def credit(app, log):
    """
    This runs every minute and calculates the total liquidity on order (rank 1) and
    each users proportion of it.
    :param log:
    :param rpc:
    :param app:
    :return:
    """
    # Set the timer going again
    credit_timer = Timer(
        60.0,
        credit,
        kwargs={'app': app, 'log': log}
    )
    credit_timer.name = 'credit_timer'
    credit_timer.daemon = True
    credit_timer.start()

    log_output = False

    # reload the config
    config.load(app, log, app.config['config_dir'], log_output)

    # calculate the credit time
    credit_time = int(time.time())

    conn = database.get_db(app)
    db = conn.cursor()
    # Get all the orders from the database.
    db.execute("SELECT * FROM orders WHERE credited=0")
    all_orders = db.fetchall()
    if len(all_orders) > 0:
        log_output = True
        log.info('Start credit')
    # store the credit time in the info table
    db.execute("UPDATE info SET value=%s WHERE key=%s", (
        credit_time,
        'last_credit_time'
    ))

    # set up for some stats
    # build the blank meta stats object
    meta = {'last-credit-time': credit_time,
            'number-of-users-active': 0,
            'number-of-orders': 0}
    db.execute("SELECT value FROM info WHERE key=%s", ('next_payout_time',))
    meta['next-payout-time'] = int(db.fetchone()[0])
    db.execute("SELECT COUNT(id) FROM users")
    meta['number-of-users'] = int(db.fetchone()[0])
    # create a list of active users
    active_users = []

    # de-duplicate the orders
    deduped_orders = deduplicate_orders(all_orders, db)

    # calculate the liquidity totals
    totals = get_total_liquidity(app, deduped_orders)

    # We've calculated the totals so submit them as liquidity_info
    Thread(
        target=liquidity_info,
        kwargs={'app': app, 'totals': totals, 'log': log}
    ).start()

    # calculate the round rewards based on percentages of target and ratios of side and
    # rank
    rewards = calculate_reward(app, totals)

    # parse the orders
    for order in deduped_orders:
        # save some stats
        meta['number-of-orders'] += 1
        if order[1] not in active_users:
            meta['number-of-users-active'] += 1
            active_users.append(order[1])
        # calculate the details
        reward, percentage = calculate_order_reward(order, totals, rewards)
        # and save to the database
        db.execute(
            "INSERT INTO credits (time,key,exchange,unit,rank,side,order_id,provided,"
            "percentage,reward,paid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (credit_time, order[1], order[8], order[9], order[2], order[5], order[0],
             order[4], (percentage * 100), reward, 0)
        )
        # update the original order too to indicate that it has been credited
        db.execute("UPDATE orders SET credited=%s WHERE id=%s", (1, order[0]))

    # write the stats to the database
    stats_config = {}
    for ex in app.config['exchanges']:
        stats_config[ex] = {}
        for unit in app.config['{}.units'.format(ex)]:
            stats_config[ex][unit] = {
                'target': app.config['{}.{}.target'.format(ex, unit)],
                'reward': app.config['{}.{}.reward'.format(ex, unit)]
            }
            for side in ['ask', 'bid']:
                stats_config[ex][unit][side] = {
                    'ratio': app.config['{}.{}.{}.ratio'.format(
                        ex,
                        unit,
                        side
                    )]
                }
                for rank in app.config['{}.{}.{}.ranks'.format(ex, unit, side)]:
                    stats_config[ex][unit][side][rank] = {
                        'ratio': app.config['{}.{}.{}.{}.ratio'.format(
                            ex,
                            unit,
                            side,
                            rank
                        )]
                    }

    db.execute("INSERT INTO stats (time,meta,totals,rewards,config) VALUES (%s,%s,%s,"
               "%s,%s)",
               (credit_time, json.dumps(meta), json.dumps(totals), json.dumps(rewards),
                json.dumps(stats_config)))
    conn.commit()
    conn.close()
    if log_output:
        log.info('End credit')
    return


def deduplicate_orders(all_orders, db):
    """
    for a list of orders, return the deduplicated list of orders
    :param all_orders:
    :param db:
    :return:
    """
    deduped_orders = []
    known_orders = []
    for order in all_orders:
        # hash the order to avoid duplicates
        # order_id, order_amount, side, exchange, unit
        order_hash = '{}.{}.{}.{}.{}'.format(order[3], order[4],
                                             order[5], order[6],
                                             order[7])
        # check if the order exists in our known orders list
        if order_hash in known_orders:
            # if this is a duplicate order, mark it as such in the database
            db.execute("UPDATE orders SET credited=%s WHERE id=%s", (-1, order[0]))
            continue
        # add the hash, as it is known
        known_orders.append(order_hash)
        # save the full order in our deduped list
        deduped_orders.append(order)
    return deduped_orders


def get_total_liquidity(app, orders):
    """
    Given a list of orders from the database, calculate the liquidity totals for unit
    side and rank
    :param app:
    :param orders:
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
            liquidity[exchange][unit]['total'] = 0.00
            for side in ['ask', 'bid']:
                liquidity[exchange][unit][side] = {'total': 0.00}
                for rank in app.config['{}.{}.{}.ranks'.format(exchange, unit, side)]:
                    liquidity[exchange][unit][side][rank] = 0.00

    # parse the orders and update the liquidity object accordingly
    for order in orders:
        # exchange.unit.total
        liquidity[order[8]][order[9]]['total'] += float(order[4])
        # exchange.unit.side.total
        liquidity[order[8]][order[9]][order[5]]['total'] += float(order[4])
        # exchange.unit.side.rank
        liquidity[order[8]][order[9]][order[5]][order[2]] += float(order[4])

    return liquidity


def calculate_reward(app, totals):
    """
    Calculate the reward for the exchange/pair/side/rank based on percentage of liquidity
    target filled and ratio of sides/ranks
    :param app:
    :param totals:
    :return:
    """
    # build the blank object
    rewards = {}
    for exchange in app.config['exchanges']:
        if exchange not in rewards:
            rewards[exchange] = {}
        for unit in app.config['{}.units'.format(exchange)]:
            if unit not in rewards[exchange]:
                rewards[exchange][unit] = {}
            for side in ['ask', 'bid']:
                rewards[exchange][unit][side] = {}
                # reward depends on the percentage of the target liquidity being provided
                total_liq = float(totals[exchange][unit]['total'])
                target_liq = float(app.config['{}.{}.target'.format(exchange, unit)])
                target_percentage = total_liq / target_liq
                if target_percentage > 1.00:
                    target_percentage = 1.00
                for rank in app.config['{}.{}.{}.ranks'.format(exchange, unit, side)]:
                    # reward is split by the rank and side ratios
                    reward = float(app.config['{}.{}.reward'.format(exchange, unit)])
                    side_ratio = float(app.config['{}.{}.{}.ratio'.format(exchange,
                                                                          unit,
                                                                          side)])
                    rank_ratio = float(app.config['{}.{}.{}.{}.ratio'.format(exchange,
                                                                             unit,
                                                                             side,
                                                                             rank)])
                    rewards[exchange][unit][side][rank] = round(((reward * side_ratio) *
                                                                rank_ratio) *
                                                                target_percentage, 8)
    return rewards


def calculate_order_reward(order, totals, rewards):
    """
    Calculate the rewards for the given order
    :param order: an order to use for the calculation
    :param totals: the total liquidity dict
    :param rewards: the rewards dict
    :return:
    """
    provided = float(order[4])
    # total liquidity = total[exchange][unit][side][rank]
    total_liquidity = float(totals[order[8]][order[9]][order[5]][order[2]])
    # Calculate the percentage of the total
    percentage = (provided / total_liquidity) if total_liquidity > 0.00 else 0.00
    # calculate the reward for this order
    reward = percentage * float(rewards[order[8]][order[9]][order[5]][order[2]])
    return reward, percentage


def liquidity_info(app, log, totals):
    """
    Calculate the current amount of liquidity in ranks 1 and 2 and submit them to Nu
    :param totals:
    :param log:
    :param rpc:
    :param app:
    :return:
    """
    rpc = get_rpc(app, log)
    for exchange in app.config['exchanges']:
        for unit in app.config['{}.units'.format(exchange)]:
            for rank in app.config['{}.{}.bid.ranks'.format(exchange, unit)]:
                identifier = "1:{}:{}:{}.{}".format(
                    'NBT{}'.format(unit.upper()),
                    exchange,
                    app.config['pool.name'],
                    rank
                )
                if rpc is not None:
                    try:
                        # get a connection to the nud rpc interface

                        rpc.liquidityinfo(
                            'B',
                            totals[exchange][unit]['bid'][rank],
                            totals[exchange][unit]['ask'][rank],
                            app.config['pool.grant_address'],
                            identifier
                        )
                    except JSONRPCException as e:
                        log.error('Sending liquidity info failed: {}'.format(e.message))
                    log.info(
                        'sent liquidity info for %s: ask=%s, bid=%s',
                        identifier,
                        totals[exchange][unit]['ask'][rank],
                        totals[exchange][unit]['bid'][rank]
                    )
