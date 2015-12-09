#! /usr/bin/env python
import random

import sys
import json
import time
import urllib
import urllib2
import requests


class Bittrex(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "bittrex"

    @staticmethod
    def validate_request(user, unit, req, sign):
        """
        validate the orders request for Bittrex
        :param user: API key
        :param unit: Currency code
        :param req: dict of data tpo send to exchange api
        :param sign: calculated sign of params
        :return: valid dict containing orders list or message of failure
        """
        url = 'https://bittrex.com/api/v1.1/market/getopenorders?' \
              'apikey={}&nonce={}&market={}'.format(user, req['nonce'], req['market'])
        r = requests.post(url=url, headers={'apisign': sign})
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text)}
        if not data['success']:
            return {'orders': [], 'message': 'invalid response'}
        valid = {'orders': [], 'message': 'success'}
        for order in data['result']:
            if 'LIMIT' not in order['OrderType']:
                continue
            valid['orders'].append({'id': order['OrderUuid'],
                                    'amount': order['Quantity'],
                                    'price': order['Limit'],
                                    'side': 'bid' if 'BUY' in order['OrderType'] else
                                    'ask'})
        if not valid['orders']:
            return {'orders': [], 'message': 'no orders found'}
        return valid


class Poloniex(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "poloniex"

    @staticmethod
    def validate_request(user, unit, req, sign):
        url = 'https://poloniex.com/tradingApi'
        headers = {'Key': user, 'Sign': sign}
        r = requests.post(url=url, headers=headers, data=json.loads(req))
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text)}
        if 'error' in data:
            return {'orders': [], 'message': data['error']}
        valid = {'orders': [], 'message': 'success'}
        for order in data:
            valid.orders.append({'id': order['orderNumber'],
                                 'side': 'ask' if order['type'] == 'sell' else 'bid',
                                 'price': float(order['rate']),
                                 'amount': float(order['amount'])})
        if not valid['orders']:
            return {'orders': [], 'message': 'no orders found'}
        return valid


class CCEDK(object):

    def __init__(self):
        self.pair_id = {}
        self.currency_id = {}
        failed = False
        while not self.pair_id or not self.currency_id:
            try:
                response = None
                if not self.pair_id:
                    url = 'https://www.ccedk.com/api/v1/stats/marketdepthfull'
                    response = json.loads(urllib2.urlopen(urllib2.Request(url), timeout=15).read())
                    for unit in response['response']['entities']:
                        if unit['pair_name'][:4] == 'nbt/':
                            self.pair_id[unit['pair_name'][4:]] = unit['pair_id']
                if not self.currency_id:
                    url = 'https://www.ccedk.com/api/v1/currency/list'
                    response = json.loads(urllib2.urlopen(urllib2.Request(url), timeout=15).read())
                    for unit in response['response']['entities']:
                        self.currency_id[unit['iso'].lower()] = unit['currency_id']
            except Exception as e:
                if response and not response['response']:
                    self.adjust(",".join(response['errors'].values()))
                    if failed:
                        print >> sys.stderr, "could not retrieve ccedk ids, will adjust shift to", self._shift, \
                            "reason:", ",".join(response['errors'].values())
                else:
                    print >> sys.stderr, "could not retrieve ccedk ids, server is unreachable", e
                failed = True
                time.sleep(1)

    def __repr__(self):
        return "ccedk"

    def validate_request(self, key, unit, data, sign):
        headers = {"Content-type": "application/x-www-form-urlencoded", "Key": key, "Sign": sign}
        url = 'https://www.ccedk.com/api/v1/order/list'
        response = json.loads(urllib2.urlopen(urllib2.Request(url, urllib.urlencode(data), headers), timeout=5).read())
        if response['errors'] is True:
            response['error'] = ",".join(response['errors'].values())
            return response
        if not response['response']['entities']:
            response['response']['entities'] = []
        validation = [{
                      'id': int(order['order_id']),
                      'price': float(order['price']),
                      'type': 'ask' if order['type'] == 'sell' else 'bid',
                      'amount': float(order['volume']),
                      } for order in response['response']['entities'] if order['pair_id'] == self.pair_id[unit.lower()]]
        return validation


class BTER(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "bter"

    def validate_request(self, user, unit, req, sign):
        """
        Submit Bter get_orders request and return order list
        :param user: API Public Key
        :param unit: Currency
        :param req: Dict of data to send to Bter
        :param sign: Calculated sign hash
        :return: order list
        """
        # Set the headers for the request
        headers = {'Sign': sign,
                   'Key': user,
                   "Content-type": "application/x-www-form-urlencoded"}
        # Send the data to the APi
        r = requests.post('https://bter.com/api/1/private/orderlist',
                          data=json.loads(req),
                          headers=headers)
        # Catch potential errors
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text)}
        if 'result' not in data:
            return {'orders': [], 'message': 'invalid response'}
        if not data['result']:
            return {'orders': [], 'message': data['message']}
        if not data['orders']:
            return {'orders': [], 'message': 'no orders'}
        valid = {'orders': [], 'message': 'success'}
        # Parse the orders to get the info we want
        for order in data['orders']:
            if order['pair'] != 'nbt_' + unit.lower():
                continue
            valid['orders'].append({'id': order['oid'],
                                    'price': float(order['rate']),
                                    'side': 'ask' if
                                    order['buy_type'].lower() == unit.lower() else
                                    'bid',
                                    'amount': (float(order['amount']) / 1.0) if
                                    order['buy_type'].lower() == unit.lower() else
                                    float(order['rate'])})
        if not valid['orders']:
            return {'orders': [], 'message': 'no orders found'}
        return valid


class TestExchange(object):

    def __init__(self):
        pass

    def __repr__(self):
        return 'test_exchange'

    @staticmethod
    def validate_request(key, unit, data, sign):
        orders = []
        for x in xrange(10):
            orders.append({'price': (1 + (random.randint(-10, 10)/10)),
                           'id': (x + random.randint(0, 250)),
                           'amount': random.randint(0, 250),
                           'side': 'bid' if int(x) % 2 == 0 else 'ask'})
        return {'orders': orders, 'message': 'success'}
