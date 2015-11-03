from threading import Timer, Thread, enumerate
import sqlite3
import time
from bitcoinrpc.authproxy import JSONRPCException
import stats

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


def credit(app, rpc, log):
    """
    This runs every minute and calculates the total liquidity on order (rank 1) and
    each users proportion of it
    :return:
    """
    # Set the timer going again
    credit_timer = Timer(60.0, credit,
                         kwargs={'app': app, 'rpc': rpc, 'log': log})
    credit_timer.name = 'credit_timer'
    credit_timer.daemon = True
    credit_timer.start()

    log.info('Start Credit')

    # calculate the credit time
    credit_time = int(time.time())

    conn = sqlite3.connect('pool.db')
    db = conn.cursor()
    # Get all the orders from the database.
    all_orders = db.execute("SELECT * FROM orders WHERE credited=0").fetchall()
    # store the credit time in the info table
    db.execute("UPDATE info SET value=? WHERE key=?", (credit_time, 'last_credit_time'))

    # de-duplicate the orders
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
            db.execute("UPDATE orders SET credited=-1 WHERE id=?", (order[0],))
            continue
        # add it now as it is known
        known_orders.append(order_hash)
        # save the full order in our deduped list
        deduped_orders.append(order)

    # get the total amount of liquidity by rank
    total = get_total_liquidity(app, deduped_orders)

    # We've calculated the totals so submit them as liquidity_info
    Thread(target=liquidity_info, kwargs={'rpc': rpc, 'total': total, 'log': log})

    # parse the orders
    for order in deduped_orders:
        # calculate the details
        total_liquidity, percentage, reward = calculate_reward(app, order, total)
        # and save to the database
        db.execute("INSERT INTO credits (time,user,exchange,unit,rank,side,order_id,"
                   "provided,total,percentage,reward,paid) VALUES (?,?,?,?,?,?,?,?,?,?,"
                   "?,?)", (credit_time, order[1], order[6], order[7], order[2],
                            order[5], order[0], order[4], total_liquidity,
                            (percentage * 100), reward, 0))
        # update the original order too to indicate that it has been credited
        db.execute("UPDATE orders SET credited=? WHERE id=?", (1, order[0]))
    conn.commit()
    conn.close()
    log.info('End Credit')
    stats.stats(app, log)
    return


def get_total_liquidity(app, orders):
    """
    Given a list of orders from the database, calculate the total amount of liquidity
    for the given rank
    :param orders:
    :param rank:
    :return:
    """
    # build the liquidity object
    liquidity = {'rank_1': {}, 'rank_2': {}}
    for rank in ['rank_1', 'rank_2']:
        for exchange in app.config['exchanges']:
            if exchange not in liquidity[rank]:
                liquidity[rank][exchange] = {}
            for unit in app.config['{}.units'.format(exchange)]:
                if unit not in liquidity[rank][exchange]:
                    liquidity[rank][exchange][unit] = {}
                for side in ['ask', 'bid']:
                    liquidity[rank][exchange][unit][side] = 0.00
    # parse the orders and update the liquidity object accordingly
    for order in orders:
        # order schema
        # id, user, rank, order_id, order_amount, side, exchange, unit, credited
        liquidity[order[2]][order[6]][order[7]][order[5]] += float(order[4])
    return liquidity


def calculate_reward(app, order, total):
    """
    Calculate the rewards for the given order
    :param app: The application object for accessing app.config
    :param order: an order to use for the calculation
    :param total: the total liquidity dict
    :return:
    """
    # order schema
    # id, user, rank, order_id, order_amount, side, exchange, unit, credited
    # amount provided = order_amount
    provided = float(order[4])
    # total liquidity = total[rank][exchange][unit][side]
    total_liquidity = float(total[order[2]][order[6]][order[7]][order[5]])
    # Calculate the percentage of the total
    percentage = (provided / total_liquidity) if total_liquidity > 0.00 else 0.00
    # Use the percentage to calculate the reward for this round
    # reward can be found in app.config['exchange.unit.side.rank.reward']
    reward = percentage * app.config['{}.{}.{}.{}.reward'.format(order[6], order[7],
                                                                 order[5], order[2])]
    return total_liquidity, percentage, reward


def liquidity_info(app, rpc, log,  total):
    """
    Calculate the current amount of liquidity in ranks 1 and 2 and submit them to Nu
    :return:
    """
    for exchange in total['rank_1']:
        for unit in total['rank_1'][exchange]:
            identifier = "1:{}:{}:{}".format('NBT{}'.format(unit.upper()),
                                             exchange,
                                             app.config['pool.name'])
            try:
                rpc.liquidityinfo('B', total['rank_1'][exchange][unit]['bid'],
                                  total['rank_1'][exchange][unit]['ask'],
                                  app.config['pool.grant_address'], identifier)
            except JSONRPCException as e:
                log.error('Sending rank 1 liquidity info failed: {}'.format(e.message))

    for exchange in total['rank_2']:
        for unit in total['rank_2'][exchange]:
            identifier = "2:{}:{}:{}".format('NBT{}'.format(unit.upper()),
                                             exchange,
                                             app.config['pool.name'])
            try:
                rpc.liquidityinfo('B', total['rank_2'][exchange][unit]['bid'],
                                  total['rank_2'][exchange][unit]['ask'],
                                  app.config['pool.grant_address'], identifier)
            except JSONRPCException as e:
                log.error('Sending rank 2 liquidity info failed: {}'.format(e.message))
