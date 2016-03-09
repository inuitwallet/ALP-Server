import ConfigParser
import json
from os import listdir
from os.path import isfile, join
import utils

__author__ = 'sammoth'


def load(app, log, config_dir, log_output):
    """
    Helper method to load pool config
    :param config_dir:
    :param log_output:
    :param app:
    :param log:
    :return:
    """
    app.config['config_dir'] = config_dir
    pool_check = check_pool_config(join(config_dir, 'pool_config'))
    if not pool_check[0]:
        log.error('Pool config check failed: {}'.format(pool_check[1]))
        return
    if log_output:
        log.info('load pool config')
    app.config.load_config(join(config_dir, 'pool_config'))
    if log_output:
        log.info('load exchanges config(s)')
    app.config['exchanges'] = []
    app.config['units'] = []
    for exchange_file in listdir(join(config_dir, 'exchanges')):
        if not isfile(join(config_dir, 'exchanges', exchange_file)):
            continue
        exchange_config_check = check_exchange_config(join(
            config_dir, 'exchanges', exchange_file
        ))
        if not exchange_config_check[0]:
            log.error('Exchange config check failed: {}'.format(exchange_config_check[1]))
        with open(join(config_dir, 'exchanges', exchange_file)) as exchange:
            exchange_dict = json.load(exchange)
            app.config.load_dict(exchange_dict)

            # we've loaded the raw configs using the bottle helpers
            # now we need to parse out some lists from the exchange data
            for ex in exchange_dict:
                # build a list of supported exchanges
                if ex not in app.config['exchanges']:
                    app.config['exchanges'].append(ex)
                    app.config['{}.units'.format(ex)] = []
                for unit in exchange_dict[ex]:
                    # build a list of supported units
                    if unit not in app.config['units']:
                        app.config['units'].append(unit)
                    # and a list of units supported on each exchange
                    app.config['{}.units'.format(ex)].append(unit)
                    # lastly, add a list of ranks by side on each exchange.unit
                    for side in ['ask', 'bid']:
                        app.config['{}.{}.{}.ranks'.format(ex, unit, side)] = []
                        for rank in exchange_dict[ex][unit][side]:
                            if rank == 'ratio':
                                continue
                            if rank not in app.config['{}.{}.{}.ranks'.format(ex,
                                                                              unit,
                                                                              side)]:
                                app.config['{}.{}.{}.ranks'.format(ex,
                                                                   unit,
                                                                   side)].append(rank)
        exchange.close()


def check_pool_config(config_file):
    """
    Check that the pool config file contains the correct elements
    :param config_file:
    :return:
    """
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    try:
        config.get('pool', 'name')
        config.get('pool', 'grant_address')
        config.get('pool', 'minimum_payout')
        config.get('rpc', 'user')
        config.get('rpc', 'pass')
        config.get('rpc', 'host')
        config.get('rpc', 'port')
        config.get('db', 'name')
        config.get('db', 'user')
        config.get('db', 'pass')
        config.get('db', 'host')
        config.get('db', 'port')
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
        return False, e.message
    return True, 'All complete'


def check_exchange_config(config_file):
    """
    Check that each exchange config file is valid
    :param config_file:
    """
    try:
        config = json.load(open(config_file))
    except ValueError:
        return False, '{} is not valid json'.format(config_file)
    for ex in config:
        # check that the exchange is supported
        if ex not in utils.supported_exchanges():
            return False, '{} is not a supported exchange'.format(ex)
        for unit in config[ex]:
            # make sure the unit section has a reward
            if 'reward' not in config[ex][unit]:
                return False, 'There is no reward set for {}.{}'.format(ex, unit)
            # ensure the reward is not negative
            if config[ex][unit]['reward'] <= 0:
                return False, 'The reward set for {}.{} is incorrect'.format(ex, unit)
            # make sure the unit has a target
            if 'target' not in config[ex][unit]:
                return False, 'There is no target set for {}.{}'.format(ex, unit)
            # ensure the target is not negative
            if config[ex][unit]['target'] <= 0:
                return False, 'The target set for {}.{} is incorrect'.format(ex, unit)
            # ensure there is an 'ask' section
            if 'ask' not in config[ex][unit]:
                return False, "{}.{} has no 'ask' details".format(ex, unit)
            # ensure there is a 'bid' section
            if 'bid' not in config[ex][unit]:
                return False, "{}.{} has no 'bid' details".format(ex, unit)
            # ensure 'ask' section has a ratio
            if 'ratio' not in config[ex][unit]['ask']:
                return False, 'There is no ratio set for {}.{}.ask'.format(ex, unit)
            # ensure 'ask' ratio is correct
            if config[ex][unit]['ask']['ratio'] <= 0:
                return False, 'The ratio set for {}.{}.ask is incorrect'.format(ex, unit)
            # ensure 'bid' section has a ratio
            if 'ratio' not in config[ex][unit]['bid']:
                return False, 'There is no ratio set for {}.{}.bid'.format(ex, unit)
            # ensure 'bid' ratio is correct
            if config[ex][unit]['bid']['ratio'] <= 0:
                return False, 'The ratio set for {}.{}.bid is incorrect'.format(ex, unit)
            # ensure ask and bid ratio add up to 1.0
            if config[ex][unit]['ask']['ratio'] + config[ex][unit]['bid']['ratio'] != 1.0:
                return False, "The ask and bid ratios don't add up to 1.0"

    return True, 'All complete'

