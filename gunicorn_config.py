import pool_server

__author__ = 'sammoth'


def on_starting(server):
    # Set the timer for credits
    pool_server.run_credit_timer()
    # Set the timer for payouts
    pool_server.run_payout_timer()
