# -*- coding: utf-8 -*-
try:
    from collections import OrderedDict
except ImportError:
    from .vendor.odict import OrderedDict

try:
    from ConfigParser import ConfigParser, NoOptionError
except ImportError:
    from .vendor.ConfigParser import ConfigParser, NoOptionError


def urllib_encode(params):
    try:
        import urllib
        return urllib.urlencode(params, True)
    except ImportError:
        from PyQt4 import QtCore
        return '&'.join([
            "{0}={1}".format(k, QtCore.QUrl.toPercentEncoding(v))
            for (k, v)
            in params.items()
        ])
