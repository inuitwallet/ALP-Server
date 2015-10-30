#! /usr/bin/env python
import random

import sys
import json
import time
import urllib
import urllib2
import httplib
import datetime


class Bittrex(object):

    def __init__(self):
        self.placed = {}
        self.closed = []

    def __repr__(self):
        return "bittrex"

    def validate_request(self, key, unit, data, sign):
        orders = []
        last_error = ""
        requests = json.loads(data['requests'])
        signs = json.loads(data['signs'])
        if len(requests) != len(signs):
            return {
                'error': 'missmatch between requests and signatures (%d vs %d)' % (len(data['requests']), len(signs))}
        if len(requests) > 2:
            return {'error': 'too many requests received: %d' % len(requests)}
        connection = httplib.HTTPSConnection('bittrex.com', timeout=5)
        for data, sign in zip(requests, signs):
            uuid = data.split('=')[-1]
            if not uuid in self.closed:
                headers = {'apisign': sign}
                connection.request('GET', data, headers=headers)
                response = json.loads(connection.getresponse().read())
                if response['success']:
                    try:
                        opened = int(
                            datetime.datetime.strptime(response['result']['Opened'], '%Y-%m-%dT%H:%M:%S.%f').strftime(
                                "%s"))
                    except:
                        opened = 0
                    try:
                        closed = int(
                            datetime.datetime.strptime(response['result']['Closed'], '%Y-%m-%dT%H:%M:%S.%f').strftime(
                                "%s"))
                    except:
                        closed = sys.maxint
                    if closed < time.time() - 60:
                        self.closed.append(uuid)
                    orders.append({
                        'id': response['result']['OrderUuid'],
                        'price': response['result']['Limit'],
                        'type': 'ask' if 'SELL' in response['result']['Type'] else 'bid',
                        'amount': response['result']['QuantityRemaining'],
                        # if not closed == sys.maxint else response['result']['Quantity'],
                        'opened': opened,
                        'closed': closed,
                    })
                else:
                    last_error = response['message']
        if not orders and last_error != "":
            return {'error': last_error}
        return orders


class Poloniex(object):

    def __init__(self):
        pass

    def __repr__(self):
        return "poloniex"

    @staticmethod
    def validate_request(key, unit, data, sign):
        headers = {'Sign': sign, 'Key': key}
        ret = urllib2.urlopen(urllib2.Request('https://poloniex.com/tradingApi',
                                              urllib.urlencode(data), headers),
                              timeout=5)
        response = json.loads(ret.read())
        if 'error' in response:
            return response
        return [{'id': int(order['orderNumber']),
                 'price': float(order['rate']),
                 'type': 'ask' if order['type'] == 'sell' else 'bid',
                 'amount': float(order['amount']),
                 } for order in response]


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

    def validate_request(self, key, unit, data, sign):
        headers = {'Sign': sign, 'Key': key, "Content-type": "application/x-www-form-urlencoded"}
        response = self.https_request('orderlist', urllib.urlencode(data), headers, timeout=15)
        if 'result' not in response or not response['result']:
            response['error'] = response['msg'] if 'msg' in response else 'invalid response: %s' % str(response)
            return response
        if not response['orders']:
            response['orders'] = []
        return [{
                    'id': int(order['oid']),
                    'price': float(order['rate']),
                    'type': 'ask' if order['buy_type'].lower() == unit.lower() else 'bid',
                    'amount': float(order['amount']) / (
                        1.0 if order['buy_type'].lower() == unit.lower() else float(order['rate'])),
                } for order in response['orders'] if order['pair'] == 'nbt_' + unit.lower()]


class TestExchange(object):

    def __init__(self):
        pass

    def __repr__(self):
        return 'test_exchange'

    @staticmethod
    def validate_request(key, unit, data, sign):
        orders = []
        for x in xrange(10):
            orders.append({'price': (1234 + random.randint(-5, 5)),
                           'id': (x + random.randint(0, 250)),
                           'amount': 10,
                           'type': 'bid' if int(x) % 2 == 0 else 'ask'})
        return orders
