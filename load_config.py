import json

__author__ = 'sammoth'


def load(app, config_file):
    with open(config_file) as fp:
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
                           format(exchange,
                                  unit,
                                  side)] = config[exchange][unit][side]['tolerance']
                for tier in ['tier_1', 'tier_2']:
                    app.config['{}.{}.{}.{}.reward'.
                               format(exchange,
                                      unit,
                                      side,
                                      tier)] = config[exchange][unit][side][tier]['reward']

