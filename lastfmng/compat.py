# -*- coding: utf-8 -*-
from PyQt4 import QtCore

from picard import PICARD_VERSION
from picard.webservice import XmlWebService

try:
    from collections import OrderedDict
except ImportError:
    from .vendor.odict import OrderedDict

try:
    from ConfigParser import ConfigParser, NoOptionError
except ImportError:
    from .vendor.ConfigParser import ConfigParser, NoOptionError


def urlencode(params):
    from PyQt4 import QtCore
    return '&'.join([
        "{0}={1}".format(k, QtCore.QUrl.toPercentEncoding(v))
        for (k, v)
        in params.items()
    ])
