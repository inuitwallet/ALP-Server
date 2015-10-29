import json
from threading import Timer
import sqlite3
from bitcoinrpc.authproxy import JSONRPCException

__author__ = 'sammoth'


def pay(rpc, log):
    """
    Pay all users who have a balance > 1 NBT
    :return:
    """
    # reset timer
    Timer(86400.0, pay, kwargs={'rpc': rpc, 'log': log}).start()
    log.info('Payout')
    # get the credit details from the database
    conn = sqlite3.connect('pool.db')
    db = conn.cursor()
    rewards = db.execute("SELECT c.id,c.user,c.reward,u.address "
                         "FROM credits AS c INNER JOIN users AS u on "
                         "u.user=c.user WHERE c.tier=1 AND c.paid=0").fetchall()
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
