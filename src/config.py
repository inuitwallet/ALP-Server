import json
from os import listdir
from os.path import isfile, join

__author__ = 'sammoth'


def load(app, log, log_output):
    """
    Helper method to load pool config
    :param app:
    :param log:
    :return:
    """
    if log_output:
        log.info('load pool config')
    app.config.load_config(join('config', 'pool_config'))
    if log_output:
        log.info('load exchanges config')
    app.config['exchanges'] = []
    app.config['units'] = []
    for exchange_file in listdir(join('config', 'exchanges')):
        if not isfile(join('config', 'exchanges', exchange_file)):
            continue
        with open(join('config', 'exchanges', exchange_file)) as exchange:
            exchange_dict = json.load(exchange)
            app.config.load_dict(exchange_dict)
            for ex in exchange_dict:
                if ex not in app.config['exchanges']:
                    app.config['exchanges'].append(ex)
                    app.config['{}.units'.format(ex)] = []
                for unit in exchange_dict[ex]:
                    if unit not in app.config['units']:
                        app.config['units'].append(unit)
                    app.config['{}.units'.format(ex)].append(unit)
        exchange.close()
