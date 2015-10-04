import json

__author__ = 'sammoth'


def load(app):
    with open('exchange_config') as fp:
        config = json.load(fp)
        fp.close()

    app.config['exchanges'] = []
    for exchange in config:
        app.config['exchanges'].append(exchange)
        app.config['{}.units'.format(exchange)] = []
        for unit in config[exchange]:
            app.config['{}.units'.format(exchange)].append(unit)
            for side in config[exchange][unit]:
                app.config['{}.{}.{}.tolerance'.
                           format(exchange, unit, side)] = config[exchange][unit][side][
                    'tolerance']
                app.config['{}.{}.{}.reward'.
                           format(exchange, unit, side)] = config[exchange][unit][side][
                    'reward']