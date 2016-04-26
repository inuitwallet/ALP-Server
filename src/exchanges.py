#! /usr/bin/env python
import json
import random
import time
import requests


class Bittrex(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "bittrex"

    @staticmethod
    def validate_request(**kwargs):
        """
        validate the orders request for Bittrex
        :param kwargs dict of arguments. should contain user, req and sign
        :return: valid dict containing orders list or message of failure
        """
        user = kwargs.get('user')
        req = kwargs.get('req')
        sign = kwargs.get('sign')
        url = 'https://bittrex.com/api/v1.1/market/getopenorders?' \
              'market={}&apikey={}&nonce={}'.format(req['market'], user, req['nonce'])
        r = requests.post(url=url,
                          headers={'apisign': sign})
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text),
                    'success': False}
        if 'success' not in data:
            return {'orders': [], 'message': 'invalid response', 'success': False}
        if not data['success']:
            return {
                'orders': [],
                'message': 'error returned: {}'.format(data['message']),
                'success': False
            }
        valid = {'orders': [], 'message': 'success', 'success': True}
        for order in data['result']:
            if 'LIMIT' not in order['OrderType']:
                continue
            valid['orders'].append({'id': order['OrderUuid'],
                                    'amount': order['Quantity'],
                                    'price': order['Limit'],
                                    'side': 'bid' if 'BUY' in order['OrderType'] else
                                    'ask'})
        if not valid['orders']:
            return {'orders': [], 'message': 'no orders found', 'success': True}
        return valid


class Poloniex(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "poloniex"

    @staticmethod
    def validate_request(**kwargs):
        user = kwargs.get('user')
        req = kwargs.get('req')
        sign = kwargs.get('sign')
        url = 'https://poloniex.com/tradingApi'
        headers = {'Key': user, 'Sign': sign}
        r = requests.post(url=url,
                          headers=headers,
                          data=req)
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text),
                    'success': False}
        if 'error' in data:
            try:
                message = json.dumps(data['error'])
            except ValueError:
                message = data['error']
            return {'orders': [], 'message': message, 'success': False}
        valid = {'orders': [], 'message': 'success', 'success': True}
        for order in data:
            valid['orders'].append({'id': order['orderNumber'],
                                    'side': 'ask' if order['type'] == 'sell' else 'bid',
                                    'price': float(order['rate']),
                                    'amount': float(order['amount'])})
        if not valid['orders']:
            return {'orders': [], 'message': 'no orders found', 'success': True}
        return valid


class CCEDK(object):

    def __init__(self):
        self.pair_id = self.get_pair_id()

    def __repr__(self):
        return "ccedk"

    @staticmethod
    def get_pair_id():
        url = 'https://www.ccedk.com/api/v1/stats/marketdepthfull'
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException):
            return None
        if 'response' not in data:
            return None
        if 'entities' not in data['response']:
            return None
        pair_id = {}
        for unit in data['response']['entities']:
            if unit['pair_name'][:6] == 'usnbt/':
                pair_id[unit['pair_name'][6:]] = unit['pair_id']
        return pair_id

    def validate_request(self, **kwargs):
        user = kwargs.get('user')
        req = kwargs.get('req')
        sign = kwargs.get('sign')
        unit = kwargs.get('unit')
        count = 0
        while self.pair_id[unit] is None:
            if count > 5:
                return {
                    'orders': [],
                    'message': 'unable to get pair id from ccedk api',
                    'success': False
                }
            self.pair_id = self.get_pair_id()
            count += 1
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Key": user,
                   "Sign": sign}
        url = 'https://www.ccedk.com/api/v1/order/list'
        r = requests.post(url=url,
                          data=req,
                          headers=headers)
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text),
                    'success': False}
        if data['errors']:
            try:
                message = json.dumps(data['errors'])
            except ValueError:
                message = data['errors']
            return {'orders': [], 'message': message, 'success': False}
        if 'response' not in data:
            return {'orders': [], 'message': 'invalid response', 'success': False}
        if 'entities' not in data['response']:
            return {'orders': [], 'message': 'invalid response', 'success': False}
        if not data['response']['entities']:
            return {'orders': [], 'message': 'no orders found', 'success': True}
        valid = {'order': [], 'message': 'success', 'success': True}
        for order in data['response']['entities']:
            if order['pair_id'] != self.pair_id[unit.lower()]:
                continue
            valid['orders'].append({'id': order['order_id'],
                                    'price': float(order['price']),
                                    'side': 'ask' if order['type'] == 'sell' else 'bid',
                                    'amount': float(order['volume'])})
        if not valid['orders']:
            return {'orders': [], 'message': 'no orders found', 'success': True}
        return valid


class BTER(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "bter"

    @staticmethod
    def validate_request(**kwargs):
        """
        Submit Bter get_orders request and return order list
        :param kwargs dict of params.
        :return: order list
        """
        user = kwargs.get('user')
        req = kwargs.get('req')
        sign = kwargs.get('sign')
        unit = kwargs.get('unit')
        # Set the headers for the request
        headers = {'Sign': sign,
                   'Key': user,
                   "Content-type": "application/x-www-form-urlencoded"}
        # Send the data to the APi
        r = requests.post('https://bter.com/api/1/private/orderlist',
                          data=req,
                          headers=headers)
        # Catch potential errors
        try:
            data = r.json()
        except ValueError as e:
            return {'orders': [], 'message': '{}: {}'.format(e.message, r.text),
                    'success': False}
        if 'result' not in data:
            return {'orders': [], 'message': 'invalid response', 'success': False}
        if not data['result']:
            try:
                message = json.dumps(data['message'])
            except ValueError:
                message = data['message']
            return {'orders': [], 'message': message, 'success': False}
        if not data['orders']:
            return {'orders': [], 'message': 'no orders', 'success': True}
        valid = {'orders': [], 'message': 'success', 'success': True}
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
            return {'orders': [], 'message': 'no orders found', 'success': True}
        return valid


class TestExchange(object):

    def __init__(self):
        pass

    def __repr__(self):
        return 'test_exchange'

    @staticmethod
    def validate_request(**kwargs):
        orders = []
        for x in xrange(10):
            orders.append({'price': (1 + (random.randint(-10, 10)/10)),
                           'id': (x + random.randint(0, 250)),
                           'amount': random.randint(0, 250),
                           'side': 'bid' if int(x) % 2 == 0 else 'ask'})
        return {'orders': orders, 'message': 'success'}
