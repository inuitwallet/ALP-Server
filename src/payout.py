import json
import socket
import time
from httplib import CannotSendRequest
from threading import Timer

from bitcoinrpc.authproxy import JSONRPCException
from src import database
from src.utils import get_rpc

__author__ = 'sammoth'


def pay(app, log):
    """
    Pay all users who have a balance greater than the minimum payout
    :param log:
    :param rpc:
    :param app:
    :return:
    """
    log.info('payout started')
    # get the credit details from the database
    conn = database.get_db(app)
    db = conn.cursor()
    db.execute("SELECT c.id,c.key,c.reward,u.address FROM credits AS c INNER JOIN "
               "users AS u on u.key=c.key WHERE c.paid=0")
    rewards = db.fetchall()
    # Calculate the total credit for each unique address
    user_rewards = {}
    for reward in rewards:
        if reward[3] not in user_rewards:
            user_rewards[reward[3]] = 0.00
        user_rewards[reward[3]] += float(reward[2])
    # remove those which don't meet the minimum payout threshold
    # and round to 6dp
    user_payouts = user_rewards.copy()
    for address in user_rewards:
        if user_rewards[address] < float(app.config['pool.minimum_payout']):
            del(user_payouts[address])
            continue
        user_payouts[address] = round(float(user_payouts[address]), 6)
    if not user_payouts:
        log.info('no-one to payout to: %s', user_rewards)
        timer_time = 86400.0
    else:
        # SendMany from nud. Report any error to log output
        try:
            # get an rpc connection
            rpc = get_rpc(app, log)
            rpc.sendmany("", user_payouts)
            log.info('payout successful: \'%s\'', json.dumps(user_payouts))
            # mark credits to paid addresses as paid
            for reward in rewards:
                if reward[3] in user_payouts:
                    db.execute('UPDATE credits SET paid=1 WHERE id=%s', (reward[0],))
            # set the timer for the next payout
            timer_time = 86400.0
        except JSONRPCException as e:
            log.error('Payout failed - %s: \'%s\'', e.message, json.dumps(user_payouts))
            timer_time = 120.0
        except (socket.error, CannotSendRequest, ValueError):
            log.error('Payout failed - no connection with nud: \'%s\'', json.dumps(
                    user_payouts))
            timer_time = 120.0
    # reset timer
    payout_timer = Timer(timer_time, pay,
                         kwargs={'app': app, 'log': log})
    payout_timer.name = 'payout_timer'
    payout_timer.daemon = True
    payout_timer.start()
    # update the next payout time
    db.execute('UPDATE info SET value=%s WHERE key=%s', (int(time.time() + timer_time),
                                                         'next_payout_time'))
    conn.commit()
    conn.close()
