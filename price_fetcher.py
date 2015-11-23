import json
from threading import Thread, Timer
import uuid
import requests
import zmq

__author__ = 'woolly_sammoth'


class PriceFetcher(object):
    """
    This object allows for connection and subscription to the NuBot price streamer.
    This ensures that NuBot and the ALP server are working with the same price and
    should mean a better $1 peg.
    The health of the connection is checked every 30 seconds. If the health check
    fails, a normal price feed is used to get the price.
    """

    def __init__(self, unit, logger):
        """
        Initialise the properties of the PriceFetcher object
        :return:
        """
        # The unit this price fetcher subscribes for
        self.unit = unit
        # logger allows us to notify of price changes
        self.log = logger
        # this context is used for all the sockets that are created
        self.context = zmq.Context()
        # These are server related properties
        self.protocol = 'tcp'
        self.base_url = 'stream.tradingbot.nu'
        self.ping_port = 5555
        self.main_port = 5556
        self.secondary_port = 8889
        self.currency_port = None
        # these properties are used during the subscription
        self.session_id = uuid.uuid4()
        self.currency_token = None
        self.ping = False
        self.price = None
        # these properties are used to control the subscription
        self.sub = True
        self.terminate = None

    def subscribe(self):
        """
        Perform the necessary steps to verify the streamer server health,
        request a token, request a subscription and finally subscribe
        :param currency:
        :return:
        """
        # send a ping? to test streamer health
        self.send_ping()
        # if there's no reply the streamer is down and we should fall back to standard
        # price fetching
        if not self.ping:
            # if there's no reply from the ping
            # get the price from a normal feed
            self.log.warn('unable to ping price streamer')
            self.price = self.normal_price_feed()
            # then set a timer to try and register again in 30 seconds
            sub_timer = Timer(30.0, self.subscribe)
            sub_timer.daemon = True
            sub_timer.start()
        # init with the streamer to get a token
        self.request_init()
        # make sure we got a token
        if self.currency_token is None:
            # if there's no valid token from the ping
            # get the price from a normal feed
            self.log.warn('price streamer didn\'t return token')
            self.price = self.normal_price_feed()
            # then set a timer to try and register again in 30 seconds
            sub_timer = Timer(30.0, self.subscribe)
            sub_timer.daemon = True
            sub_timer.start()
        # start to get the price and start subscription
        self.start()
        # make sure we got a response
        if self.price is None:
            # if there's no price from the ping
            # get the price from a normal feed
            self.log.warn('price streamer failed to return price')
            self.price = self.normal_price_feed()
            # then set a timer to try and register again in 30 seconds
            sub_timer = Timer(30.0, self.subscribe)
            sub_timer.daemon = True
            sub_timer.start()
        # finally subscribe in a thread
        sub_thread = Thread(target=self.subscription_thread)
        sub_thread.daemon = True
        sub_thread.start()
        # and set a timer thread to check the health of the server with ping?
        ping_thread = Timer(30.0, self.health_thread)
        ping_thread.daemon = True
        ping_thread.start()

    def subscription_thread(self):
        """
        Perform the subscription and price updating when necessary
        :return:
        """
        # we use a subscription socket
        subscription_socket = self.context.socket(zmq.SUB)
        # connect to the currency port
        subscription_socket.connect('{}://{}:{}'.format(self.protocol,
                                                        self.base_url,
                                                        self.currency_port))
        # self.sub initialises as True and is set False by the 'unsubscribe' method
        while self.sub:
            # wait for a 'shiftWalls' command and parse the new price from it
            response = subscription_socket.poll()
            if response['command'] != 'shiftWalls':
                continue
            self.price = float(response['args'][1])
            self.log.info('{} price set to {}'.format(self.unit, self.price))
        return

    def health_thread(self):
        """
        Ping periodically to check the health of the service.
        Revert to standard feeds if the pong fails
        :return:
        """
        # send the ping
        self.send_ping()
        if not self.ping:
            # if there's no reply from the ping
            # get the price from a normal feed
            self.log.warn('unable to ping price streamer')
            self.price = self.normal_price_feed()
            # then set a timer to try and register again in 30 seconds
            sub_timer = Timer(30.0, self.subscribe)
            sub_timer.daemon = True
            sub_timer.start()
        else:
            # if we got a valid reply set another timer to check again in 30 seconds
            ping_thread = Timer(30.0, self.health_thread)
            ping_thread.daemon = True
            ping_thread.start()

    def unsubscribe(self):
        """
        unsubscribe from the streamer service
        :return:
        """
        # setting this False stops the subscription_thread while loop
        self.sub = False
        # simple request socket
        cancel_socket = self.context.socket(zmq.REQ)
        # the command port is the currency port + 100
        cancel_socket.connect('{}://{}:{}'.format(self.protocol,
                                                  self.base_url,
                                                  (int(self.currency_port) + 100)))
        # set the timeouts
        cancel_socket.setsockopt(zmq.SNDTIMEO, 2000)
        cancel_socket.setsockopt(zmq.RCVTIMEO, 2000)
        # send the stop message
        cancel_socket.send('{} {} stop'.format(self.currency_token, self.session_id))
        # set the output for notifications
        self.terminate = cancel_socket.recv()
        cancel_socket.close()

    def send_ping(self):
        """
        First task is to ping the server and test it is active
        :return:
        """
        # use a simple request socket
        ping_socket = self.context.socket(zmq.REQ)
        # use the default ping port
        ping_socket.connect('{}://{}:{}'.format(self.protocol,
                                                self.base_url,
                                                self.ping_port))
        # set the timeouts
        ping_socket.setsockopt(zmq.SNDTIMEO, 2000)
        ping_socket.setsockopt(zmq.RCVTIMEO, 2000)
        # default to False
        self.ping = False
        # send the ping? request
        ping_socket.send('ping?')
        # if the server is down, we will get a zmq timeout error.
        # catch that here and handle
        try:
            response = ping_socket.recv()
        except zmq.error.Again as e:
            response = e
        # set True if we get the correct response
        if response == 'pong!':
            self.ping = True
        # remember to close the socket
        ping_socket.close()

    def request_init(self):
        """
        Once we have successfully ping/ponged, we request a token for the currency of
        interest.
        :param currency:
        :return:
        """
        # request socket
        init_socket = self.context.socket(zmq.REQ)
        # use the main port
        init_socket.connect('{}://{}:{}'.format(self.protocol,
                                                self.base_url,
                                                self.main_port))
        # set the timeouts
        init_socket.setsockopt(zmq.SNDTIMEO, 2000)
        init_socket.setsockopt(zmq.RCVTIMEO, 2000)
        # send the necessary information
        init_socket.send('{} {}:{} {}'.format(self.session_id, self.base_url,
                                              self.secondary_port, self.unit))
        # get the response as json
        response = init_socket.recv_json()
        # in case we get a different response to the one expected
        if 'args' not in response:
            init_socket.close()
            return
        # otherwise parse out the args for later use
        args = list(response['args'])
        self.currency_port = args[0]
        self.currency_token = args[1]
        init_socket.close()

    def start(self):
        """
        Instruct the streamer that we would like to subscribe.
        It responds with the price
        :return:
        """
        # request socket
        price_socket = self.context.socket(zmq.REQ)
        # currency manage port is currency_port + 100
        price_socket.connect('{}://{}:{}'.format(self.protocol,
                                                 self.base_url,
                                                 (int(self.currency_port) + 100)))
        # set the timeouts
        price_socket.setsockopt(zmq.SNDTIMEO, 2000)
        price_socket.setsockopt(zmq.RCVTIMEO, 2000)
        # send the token and our session id
        price_socket.send('{} {} start'.format(self.currency_token, self.session_id))
        response = price_socket.recv_json()
        # if we got a different response to the one we were expecting
        if 'args' not in response:
            price_socket.close()
        # otherwise set the price
        self.price = float(response['args'][1])
        self.log.info('{} price set to {}'.format(self.unit, self.price))
        price_socket.close()

    def normal_price_feed(self):
        """
        If connection to the price streamer fails for whatever reason we fall back to
        standard price feeds.
        The hierarchy of the feeds matches that set for NuBot
        :return:
        """
        # many fiat currencies share a hierarchy
        if self.unit in ['cny', 'hkd', 'php', 'jpy']:
            return self.fetch_price(['yahoo', 'google_official'])
        # Eur is the same but with bitstamp as higher
        if self.unit == 'eur':
            return self.fetch_price(['bitstamp_eur', 'yahoo', 'google_official'])
        # Bitcoin
        if self.unit == 'btc':
            return self.fetch_price(['bitfinex', 'blockchain', 'bitcoin_average',
                                     'coinbase', 'bitstamp'])
        # Peercoin
        if self.unit == 'ppc':
            return self.fetch_price(['btce', 'coinmarketcap_ne', 'coinmarketcap_no'])
        # Etherium
        if self.unit == 'eth':
            return self.fetch_price(['coinmarketcap_ne', 'coinmarketcap_no'])
        # Ripple
        if self.unit == 'xrp':
            return self.fetch_price(['coinmarketcap_ne', 'coinmarketcap_no'])
        if self.unit == 'ltc':
            return self.fetch_price(['btce', 'coinmarketcap_ne', 'coinmarketcap_no',
                                     'bitfinex'])

    def fetch_price(self, feeds):
        """
        Loop through the supplied feeds and return the first price found
        :param self:
        :param feeds:
        :return:
        """
        for feed in feeds:
            fetch_price = getattr(self, '{}'.format(feed))()
            if fetch_price is not None:
                self.log.info('fetched price from %s' % feed)
                return fetch_price
        return None

    def yahoo(self):
        """
        Yahoo Finance feed
        :return:
        """
        url = 'https://query.yahooapis.com/v1/public/yql?q=select%20*%20from%20yahoo.' \
              'finance.xchange%20where%20pair%20in%20(%22USD{}%22)&format=json&' \
              'diagnostics=false&env=store%3A%2F%2Fdatatables.org%2' \
              'Falltableswithkeys&callback='.format(self.unit.upper())
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'query' not in data:
            return None
        if 'results' not in data['query']:
            return None
        if 'rate' not in data['query']['results']:
            return None
        if 'Rate' not in data['query']['results']['rate']:
            return None
        return float(data['query']['results']['rate']['Rate'])

    def google_official(self):
        """
        Google Price feed
        :return:
        """
        url = 'http://www.google.com/finance/info?q=CURRENCY%3aUSD{}'.format(
            self.unit.upper())
        r = requests.get(url)
        # some odd characters to remove before we get json
        data = r.text.replace("//", "").replace("[", "").replace("]", "")
        try:
            data = json.loads(data)
        except ValueError:
            return None
        if 'l' not in data:
            return None
        return float(data['l'])

    def bitstamp_eur(self):
        """
        Bitstamp feed for Eur
        :return:
        """
        url = 'https://www.bitstamp.net/api/eur_usd/'
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'sell' not in data:
            return None
        if 'buy' not in data:
            return None
        return float((data['sell'] + data['buy']) / 2)

    def bitfinex(self):
        """
        bitfinex price feed
        :return:
        """
        url = 'https://api.bitfinex.com/v1/pubticker/{}usd'.format(self.unit.lower())
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'last_price' not in data:
            return None
        return float(data['last_price'])

    def blockchain(self):
        """
        blockchain price feed
        :return:
        """
        url = 'https://blockchain.info/ticker'
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'USD' not in data:
            return None
        if 'last' not in data['USD']:
            return None
        return data['USD']['last']

    def bitcoin_average(self):
        """
        Bitcoin Average price feed
        :return:
        """
        url = 'https://api.bitcoinaverage.com/ticker/global/USD'
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'last' not in data:
            return None
        return data['last']

    def coinbase(self):
        """
        Coinbase price feed
        :return:
        """
        url = 'https://coinbase.com/api/v1/prices/spot_rate?currency=USD'
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'amount' not in data:
            return None
        return data['amount']

    def bitstamp(self):
        """
        Bitstamp price feed
        :return:
        """
        url = 'https://www.bitstamp.net/api/ticker/'
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'last' not in data:
            return None
        return data['last']

    def btce(self):
        """
        BTCe price feed
        :return:
        """
        url = 'https://btc-e.com/api/2/{}_usd/ticker/'.format(self.unit.lower())
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'ticker' not in data:
            return None
        if 'last' not in data['ticker']:
            return None
        return data['ticker']['last']

    def coinmarketcap_ne(self):
        """
        coinmarketcap nexuist price feed
        :return:
        """
        url = 'http://coinmarketcap-nexuist.rhcloud.com/api/{}'.format(self.unit.lower())
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'price' not in data:
            return None
        if 'usd' not in data['price']:
            return None
        return data['price']['usd']

    def coinmarketcap_no(self):
        """
        Coinmarketcap North Pole price feed
        :return:
        """
        url = 'http://coinmarketcap.northpole.ro/api/{}.json'.format(self.unit.lower())
        r = requests.get(url)
        try:
            data = r.json()
        except ValueError:
            return None
        if 'price' not in data:
            return None
        return data['price']
