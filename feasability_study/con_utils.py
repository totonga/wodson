#!/usr/bin/env python
"""
Access ASAM Ods python using omniorb and wrap it using swagger.

Copyright (c) 2015, Andreas Krantz
License: Apache 2.0 (http://www.apache.org/licenses/LICENSE-2.0.html)

"""

__author__ = "Andreas Krantz"
__license__ = "Apache 2.0"
__version__ = "0.0.1"
__maintainer__ = "Andreas Krantz"
__email__ = "totonga@gmail.com"
__status__ = "Prototype"


def add(config, conI, params):
    if not config.has_key('cons'):
        config['cons'] = {}
    
    config['cons'][conI] = params


def list(config):
    rv = []
    if config.has_key('cons'):
        for conI in config['cons']:
            rv.append(conI)
    return rv


def delete(config, conI):
    if config.has_key('cons'):
        if config['cons'].has_key(conI):
            del config['cons'][conI]


def update(config, conI, params):
    if config.has_key('cons'):
        if config['cons'].has_key(conI):
            for param in params:
                config['cons'][conI][param] = params[param]
                return
    add(config, conI, params)


def get_params(config, conI):
    if config.has_key('cons'):
        if config['cons'].has_key(conI):
            return config['cons'][conI]
    raise SyntaxError('Con "' + conI + '" not defined')


def exists(config, conI):
    if config.has_key('cons'):
        if config['cons'].has_key(conI):
            return True
    return False
