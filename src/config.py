import json
from os import listdir
from os.path import isfile, join

__author__ = 'sammoth'


def load(app, log, log_output):
    """
    Helper method to load pool config
    :param log_output:
    :param app:
    :param log:
    :return:
    """
    if log_output:
        log.info('load pool config')
    app.config.load_config(join('config', 'pool_config'))
    if log_output:
        log.info('load exchanges config(s)')
    app.config['exchanges'] = []
    app.config['units'] = []
    for exchange_file in listdir(join('config', 'exchanges')):
        if not isfile(join('config', 'exchanges', exchange_file)):
            continue
        with open(join('config', 'exchanges', exchange_file)) as exchange:
            exchange_dict = json.load(exchange)
            app.config.load_dict(exchange_dict)

            print exchange_dict

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
