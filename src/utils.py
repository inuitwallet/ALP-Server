#! /usr/bin/env python
from _socket import error
from httplib import CannotSendRequest

import requests
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from hashlib import sha256
from binascii import unhexlify


def get_rpc(app, log):
    """
    Return a connection to the nud  rpc  interface
    """
    try:
        r = requests.get(
            "http://{}:{}@{}:{}".format(
                app.config['rpc.user'],
                app.config['rpc.pass'],
                app.config['rpc.host'],
                app.config['rpc.port']
            )
        )
        if r.status_code != requests.codes.OK:
            rpc = None
        else:
            try:
                rpc = AuthServiceProxy(
                    "http://{}:{}@{}:{}".format(
                        app.config['rpc.user'],
                        app.config['rpc.pass'],
                        app.config['rpc.host'],
                        app.config['rpc.port']
                    )
                )
            except (JSONRPCException, error, CannotSendRequest, ValueError) as e:
                log.error('Connection with nud failed: {}'.format(e))
                rpc = None
    except requests.ConnectionError as e:
        log.error('Connection with nud failed: {}'.format(e))
        rpc = None
    return rpc


def supported_exchanges():
    return [
        'bittrex',
        'poloniex',
        'ccedk',
        'bter',
        'cryptsy',
        'test_exchange',
        'liquidity_test'
    ]


class AddressCheck(object):
    def __init__(self):
        self.b58_digits = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    class Base58Error(Exception):
        pass

    class InvalidBase58Error(Base58Error):
        pass

    def check_checksum(self, key):
        try:
            check_key = self.decode(key.strip().replace(' ', ''))
        except ValueError:
            return False
        checksum = check_key[-4:]
        check_hash = sha256(sha256(check_key[:-4]).digest()).digest()[:4]
        if check_hash == checksum:
            return True
        else:
            return False

    def decode(self, s):

        if not s:
            return b''
        # Convert the string to an integer
        n = 0
        for c in s:
            n *= 58
            if c not in self.b58_digits:
                raise self.InvalidBase58Error('Character %r is not a valid base58 character' % c)
            digit = self.b58_digits.index(c)
            n += digit
        # Convert the integer to bytes
        h = '%x' % n
        if len(h) % 2:
            h = '0' + h
        res = unhexlify(h.encode('utf8'))
        # Add padding back.
        pad = 0
        for c in s[:-1]:
            if c == self.b58_digits[0]:
                pad += 1
            else:
                break
        return b'\x00' * pad + res