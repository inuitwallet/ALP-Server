import ConfigParser
import json
from os import listdir
from os.path import isfile, join

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
    Check that each exchange config file is  valid
    :param config_file:
    """
    config = json.load(open(config_file))
    return False

