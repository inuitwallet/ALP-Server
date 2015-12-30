import json
import time

from src import database

__author__ = 'sammoth'


def stats(app, log, log_output):
    """
    This method runs once every 65 seconds and stores the pool statistics to the database
    :return:
    """
    if log_output:
        log.info('Start stats collection')
    conn = database.get_db(app)
    db = conn.cursor()
    # get the last credit time
    db.execute("SELECT value FROM info WHERE key=%s", ('last_credit_time',))
    last_credit_time = int(db.fetchone()[0])
    db.execute("SELECT value FROM info WHERE key=%s", ('next_payout_time',))
    next_payout_time = int(db.fetchone()[0])
    # build the blank data object
    meta = {'last-credit-time': last_credit_time, 'number-of-users': 0,
            'number-of-users-active': 0, 'number-of-orders': 0,
            'next-payout-time': next_payout_time}
    totals = {'all': 0.0, 'bid': 0.0, 'ask': 0.0,
              'rank_1': 0.0, 'bid-rank_1': 0.0, 'ask-rank_1': 0.0,
              'rank_2': 0.0, 'bid-rank_2': 0.0, 'ask-rank_2': 0.0}
    rewards = {}
    # add variable totals based on app.config
    for exchange in app.config['exchanges']:
        totals['{}'.format(exchange)] = 0.0
        for unit in app.config['{}.units'.format(exchange)]:
            totals['{}'.format(unit)] = 0.0
            totals['{}-{}'.format(exchange, unit)] = 0.0
            for side in ['bid', 'ask']:
                totals['{}-{}'.format(exchange, side)] = 0.0
                totals['{}-{}'.format(unit, side)] = 0.0
                totals['{}-{}-{}'.format(exchange, unit, side)] = 0.0
                for rank in ['rank_1', 'rank_2']:
                    totals['{}-{}'.format(unit, rank)] = 0.0
                    totals['{}-{}-{}'.format(unit, side, rank)] = 0.0
                    totals['{}-{}'.format(exchange, rank)] = 0.0
                    totals['{}-{}-{}'.format(exchange, side, rank)] = 0.0
                    totals['{}-{}-{}-{}'.format(exchange, unit, side, rank)] = 0.0
                    rewards['{}-{}-{}-{}'.format(exchange, unit, side, rank)] = 0.0
    # get the number of users
    db.execute("SELECT COUNT(id) FROM users")
    meta['number-of-users'] = db.fetchone()[0]
    # create a list of active users
    active_users = []
    # get the latest credit data from the credits field
    db.execute("SELECT * FROM credits WHERE time=%s", (last_credit_time,))
    credit_data = db.fetchall()
    # parse the credit_data
    # credits schema:
    # id, time, user, exchange, unit, rank, side, order_id, order_price,
    # server_price, provided, total, percentage, reward, paid
    for cred in credit_data:
        # increment the number of orders
        meta['number-of-orders'] += 1
        # add newly found users to the active users list
        if cred[2] not in active_users:
            active_users.append(cred[2])
        # increment the total liquidity (this is the total over the entire pool)
        totals['all'] += float(cred[8])
        # increment side totals
        totals['{}'.format(cred[6])] += float(cred[8])
        # increment rank totals
        totals['{}'.format(cred[5])] += float(cred[8])
        # increment side/rank totals
        totals['{}-{}'.format(cred[6], cred[5])] += float(cred[8])
        # increment exchange totals
        totals['{}'.format(cred[3])] += float(cred[8])
        # increment exchange/unit totals
        totals['{}-{}'.format(cred[3], cred[4])] += float(cred[8])
        # increment exchange/side totals
        totals['{}-{}'.format(cred[3], cred[6])] += float(cred[8])
        # increment unit totals
        totals['{}'.format(cred[4])] += float(cred[8])
        # increment unit/side totals
        totals['{}-{}'.format(cred[4], cred[6])] += float(cred[8])
        # increment exchange/unit/side totals
        totals['{}-{}-{}'.format(cred[3], cred[4], cred[6])] += float(cred[8])
        # increment exchange/rank totals
        totals['{}-{}'.format(cred[3], cred[5])] += float(cred[8])
        # increment unit/rank totals
        totals['{}-{}'.format(cred[4], cred[5])] += float(cred[8])
        # increment exchange/side/rank totals
        totals['{}-{}-{}'.format(cred[3], cred[6], cred[5])] += float(cred[8])
        # increment exchange/unit/side/rank totals
        totals['{}-{}-{}-{}'.format(cred[3],
                                    cred[4],
                                    cred[6], cred[5])] += float(cred[8])
    # set the number of active users based on the credits parsed
    meta['number-of-users-active'] = len(active_users)
    # calculate the rewards
    for ex in app.config['exchanges']:
        for unit in app.config['{}.units'.format(ex)]:
            for side in ['ask', 'bid']:
                for rank in ['rank_1', 'rank_2']:
                    rewards['{}-{}-{}-{}'.format(
                        ex, unit, side, rank)] = calculate_reward(
                        app.config['{}.{}.{}.{}.reward'.format(ex, unit, side, rank)],
                        totals['{}-{}-{}-{}'.format(ex, unit, side, rank)])
    # save the details to the database
    db.execute("INSERT INTO stats (time,meta,totals,rewards) VALUES (%s,%s,%s,%s)",
               (int(time.time()), json.dumps(meta),
                json.dumps(totals), json.dumps(rewards)))
    conn.commit()
    conn.close()
    if log_output:
        log.info('End stats collection')


def calculate_reward(reward, total):
    """
    Calculate the reward per NBT given the two parameters
    :param reward:
    :param total:
    :return:
    """
    return round(float(reward) / float(total), 8) if float(total) > 0.0 else round(
        float(reward), 8)