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
                for rank in ['rank_1', 'rank_2']:
                    app.config['{}.{}.{}.{}.reward'.
                               format(exchange,
                                      unit,
                                      side,
                                      rank)] = config[exchange][unit][side][rank]['reward']

