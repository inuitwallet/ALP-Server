import json
from threading import Timer
import uuid
import requests
import zmq
from src import database

__author__ = 'woolly_sammoth'


class StreamerPriceFetcher(object):

    def __init__(self):
        # set the base variables
        self.protocol = 'tcp'
        self.base_url = 'stream.tradingbot.nu'
        self.ping_port = 5555
        self.main_port = 5556
        self.secondary_port = 8889
        # set a context of all sockets
        global_context = zmq.Context()
        self.context = global_context.instance()
        self.req_socket = self.build_req_socket()
        self.price = None
        self.currency_details = {}
        self.session_id = uuid.uuid4()

    def build_req_socket(self):
        # create a socket for pings
        req_socket = self.context.socket(zmq.REQ)
        # set the timeouts
        req_socket.setsockopt(zmq.SNDTIMEO, 500)
        req_socket.setsockopt(zmq.RCVTIMEO, 500)
        return req_socket

    def get_price(self, unit):
        if not self.send_ping():
            return None
        if unit not in self.currency_details:
            port, token = self.request_init(unit)
            if port is None or token is None:
                return None
            self.currency_details[unit] = {'port': port, 'token': token}
        return self.request_price(
            self.currency_details['port'],
            self.currency_details['token']
        )

    def send_ping(self):
        # use the default ping port
        self.req_socket.connect(
            '{}://{}:{}'.format(
                self.protocol,
                self.base_url,
                self.ping_port
            )
        )

        ping = False
        # send the ping? request
        self.req_socket.send('ping?')
        # if the server is down, we will get a zmq timeout error.
        # catch that here and handle
        try:
            response = self.req_socket.recv()
        except zmq.error.Again as e:
            self.req_socket.close()
            self.req_socket = self.build_req_socket()
            response = e
        # set True if we get the correct response
        if response == 'pong!':
            ping = True
        return ping

    def request_init(self, unit):
        """
        Once we have successfully ping/ponged, we request a token for the currency of
        interest.
        :param currency:
        :return:
        """
        # use the main port
        self.req_socket.connect(
            '{}://{}:{}'.format(
                self.protocol,
                self.base_url,
                self.main_port
            )
        )
        # send the necessary information
        self.req_socket.send(
            '{} {}:{} {}'.format(
                self.session_id,
                self.base_url,
                self.secondary_port,
                unit
            )
        )
        # get the response as json
        response = self.req_socket.recv_json()
        # in case we get a different response to the one expected
        if 'args' not in response:
            return None, None
        # otherwise parse out the args for later use
        args = list(response['args'])
        port = args[0]
        token = args[1]
        return port, token

    def request_price(self, port, token):
        """
        Instruct the streamer that we would like to subscribe.
        It responds with the price
        :return:
        """
        # currency manage port is currency_port + 100
        self.req_socket.connect(
            '{}://{}:{}'.format(
                self.protocol,
                self.base_url,
                int(port) + 100
            )
        )
        # send the token and our session id
        self.req_socket.send(
            '{} {} start'.format(
                token,
                self.session_id
            )
        )
        try:
            response = self.req_socket.recv_json()
        except ValueError:
            self.req_socket.close()
            self.req_socket = self.build_req_socket()
            return None
        # if we got a different response to the one we were expecting
        if 'args' not in response:
            return None
        # otherwise set the price
        return float(response['args'][1])


class StandardPriceFetcher(object):

    def get_price(self, unit):
        """
        If connection to the price streamer fails for whatever reason we fall back to
        standard price feeds.
        The hierarchy of the feeds matches that set for NuBot
        :return:
        """
        # many fiat currencies share a hierarchy
        if unit in ['cny', 'hkd', 'php', 'jpy']:
            return self.fetch_price(
                'yahoo', [
                   'google_official'
                ],
                unit
            )
        # Eur is the same but with bitstamp as higher
        if unit == 'eur':
            return self.fetch_price(
                'bitstamp_eur', [
                    'yahoo',
                    'google_official'
                ],
                unit
            )
        # Bitcoin
        if unit == 'btc':
            return self.fetch_price(
                'bitfinex', [
                    'blockchain',
                    'bitcoin_average',
                    'coinbase',
                    'bitstamp',
                    'yahoo',
                    'google_official'
                ],
                unit
            )
        # Peercoin
        if unit == 'ppc':
            return self.fetch_price(
                'btce', [
                    'coinmarketcap_ne',
                    'coinmarketcap_no'
                ],
                unit
            )
        # Etherium
        if unit == 'eth':
            return self.fetch_price(
                'coinmarketcap_ne', [
                    'coinmarketcap_no'
                ],
                unit
            )
        # Ripple
        if unit == 'xrp':
            return self.fetch_price(
                'coinmarketcap_ne', [
                    'coinmarketcap_no'
                ],
                unit
            )
        # Litecoin
        if unit == 'ltc':
            return self.fetch_price(
                'btce', [
                    'coinmarketcap_ne',
                    'coinmarketcap_no',
                    'bitfinex'
                ],
                unit
            )

    def fetch_price(self, main_feed, feeds, unit):
        """
        Loop through the supplied feeds and return the first price found
        :param unit:
        :param main_feed:
        :param self:
        :param feeds:
        :return:
        """
        main_price = float(getattr(self, '{}'.format(main_feed))(unit))
        prices = []
        for feed in feeds:
            fetch_price = getattr(self, '{}'.format(feed))(unit)
            if fetch_price is not None:
                prices.append(float(fetch_price))
        average = float(sum(prices)) / float(len(prices))
        if (main_price < (0.95 * average)) or (main_price > (1.05 * average)):
            return average
        return main_price

    @staticmethod
    def yahoo(unit):
        """
        Yahoo Finance feed
        :return:
        """
        url = 'https://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.' \
              'finance.xchange%20where%20pair%20in%20(%22USD{}%22)&format=json&' \
              'diagnostics=false&env=store%3A%2F%2Fdatatables.org%2' \
              'Falltableswithkeys&callback='.format(unit.upper())
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'query' not in data:
            return None
        if 'results' not in data['query']:
            return None
        if 'rate' not in data['query']['results']:
            return None
        if 'Rate' not in data['query']['results']['rate']:
            return None
        price = float(data['query']['results']['rate']['Rate'])
        if unit == 'btc':
            return float(1/price)
        return price

    @staticmethod
    def google_official(unit):
        """
        Google Price feed
        :return:
        """
        url = 'http://www.google.com/finance/info?q=CURRENCY%3aUSD{}'.format(
            unit.upper())
        try:
            r = requests.get(url)
            # some odd characters to remove before we get json
            data = r.text.replace("//", "").replace("[", "").replace("]", "")
            data = json.loads(data)
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'l' not in data:
            return None
        price = float(data['l'])
        if unit == 'btc':
            return float(1/price)
        return price

    @staticmethod
    def bitstamp_eur(unit):
        """
        Bitstamp feed for Eur
        :return:
        """
        url = 'https://www.bitstamp.net/api/eur_usd/'
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'sell' not in data:
            return None
        if 'buy' not in data:
            return None
        price = float((float(data['sell']) + float(data['buy'])) / float(2))
        if unit == 'eur':
            return float(1/price)
        return price

    @staticmethod
    def bitfinex(unit):
        """
        bitfinex price feed
        :return: price in nbt/btc
        """
        url = 'https://api.bitfinex.com/v1/pubticker/{}usd'.format(unit.lower())
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'last_price' not in data:
            return None
        return float(data['last_price'])

    @staticmethod
    def blockchain(unit):
        """
        blockchain price feed
        :return:
        """
        url = 'https://blockchain.info/ticker'
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'USD' not in data:
            return None
        if 'last' not in data['USD']:
            return None
        return data['USD']['last']

    @staticmethod
    def bitcoin_average(unit):
        """
        Bitcoin Average price feed
        :return:
        """
        url = 'https://api.bitcoinaverage.com/ticker/global/USD'
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'last' not in data:
            return None
        return data['last']

    @staticmethod
    def coinbase(unit):
        """
        Coinbase price feed
        :return:
        """
        url = 'https://coinbase.com/api/v1/prices/spot_rate?currency=USD'
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'amount' not in data:
            return None
        return float(data['amount'])

    @staticmethod
    def bitstamp(unit):
        """
        Bitstamp price feed
        :return:
        """
        url = 'https://www.bitstamp.net/api/ticker/'
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'last' not in data:
            return None
        return data['last']

    @staticmethod
    def btce(unit):
        """
        BTCe price feed
        :return:
        """
        url = 'https://btc-e.com/api/2/{}_usd/ticker/'.format(unit.lower())
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'ticker' not in data:
            return None
        if 'last' not in data['ticker']:
            return None
        return data['ticker']['last']

    @staticmethod
    def coinmarketcap_ne(unit):
        """
        coinmarketcap nexuist price feed
        :return:
        """
        url = 'http://coinmarketcap-nexuist.rhcloud.com/api/{}'.format(unit.lower())
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'price' not in data:
            return None
        if 'usd' not in data['price']:
            return None
        return float(data['price']['usd'])

    @staticmethod
    def coinmarketcap_no(unit):
        """
        Coinmarketcap North Pole price feed
        :return:
        """
        url = 'http://coinmarketcap.northpole.ro/api/{}.json'.format(unit.lower())
        try:
            r = requests.get(url)
            data = r.json()
        except (ValueError, requests.exceptions.RequestException, TypeError):
            return None
        if 'price' not in data:
            return None
        return float(data['price'])


class PriceFetcher(object):

    def __init__(self, app, log):
        self.log = log
        self.streamer = StreamerPriceFetcher()
        self.standard = StandardPriceFetcher()
        self.update_prices(app)

    def update_prices(self, app):
        price_timer = Timer(
            60.0,
            self.update_prices,
            kwargs={'app': app}
        )
        price_timer.name = 'price_timer'
        price_timer.daemon = True
        price_timer.start()
        conn = database.get_db(app)
        db = conn.cursor()
        for unit in app.config['units']:
            self.log.info('fetching price for {}'.format(unit))
            streamer_price = self.streamer.get_price(unit)
            if streamer_price is None:
                price = self.standard.get_price(unit)
                self.log.warn('price streamer offline!')
            else:
                price = streamer_price
            db.execute(
                "INSERT INTO prices (unit, price) VALUES (%s,%s)", (
                    unit,
                    price
                )
            )
            self.log.info('{} price set to {}'.format(unit, price))
        conn.commit()
        conn.close()

