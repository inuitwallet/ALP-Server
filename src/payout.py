import json
import time
from threading import Timer

from bitcoinrpc.authproxy import JSONRPCException
from src import database

__author__ = 'sammoth'


def pay(app, rpc, log):
    """
    Pay all users who have a balance > 1 NBT
    :return:
    """
    # reset timer
    payout_timer = Timer(86400.0, pay,
                         kwargs={'rpc': rpc, 'log': log})
    payout_timer.name = 'payout_timer'
    payout_timer.daemon = True
    payout_timer.start()
    log.info('Payout')
    # get the credit details from the database
    conn = database.get_db(app)
    db = conn.cursor()
    db.execute('UPDATE info SET value=%s WHERE key=%s', (int(time.time() + 86400),
                                                         'next_payout_time'))
    db.execute("SELECT c.id,c.user,c.reward,u.address FROM credits AS c INNER JOIN "
               "users AS u on u.user=c.user WHERE c.rank=1 AND c.paid=0")
    rewards = db.fetchall()
    conn.commit()
    conn.close()
    # Calculate the total credit for each unique address
    user_rewards = {}
    for reward in rewards:
        if reward[3] not in user_rewards:
            user_rewards[reward[3]] = 0.00
        user_rewards[reward[3]] += float(reward[2])
    # remove those which don't meet the minimum payout threshold
    for address in user_rewards:
        if user_rewards[address] < 1:
            del(user_rewards[address])
    # SendMany from nud. Report any error to log output
    try:
        rpc.sendmany("", "'{}'".format(json.dumps(user_rewards).replace(' ', '')))
        log.info('Payout succeeded')
    except JSONRPCException as e:
        log.error('Payout failed: {}'.format(e.message))
