# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

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


class PluginXmlWebService(XmlWebService):
    """
    Subclass for compatibility workarounds...

    Picard 1.4 started urlencoding the path argument, breaking any already
    encoded query parameter string. In addition the 'queryargs' parameter was
    introduced.
    """
    def get(self, host, port, path, handler, **kwargs):
        """
        Signatures...

        - Picard 1.3.x
            host, port, path, handler,
            xml=True, priority=False, important=False, mblogin=False,
            cacheloadcontrol=None, refresh=False

        - Picard 1.4.x
            host, port, path, handler,
            xml=True, priority=False, important=False, mblogin=False,
            cacheloadcontrol=None, refresh=False,
            queryargs=None
        """
        queryargs = kwargs.get('queryargs')
        if queryargs:
            if PICARD_VERSION[1] >= 4:
                # urlencode arguments.
                # for some reason they are using addEncodedQueryItem()
                # internally, instead of the one that would automatically
                # encode everything.
                kwargs.update({
                    'queryargs': {
                        k: QtCore.QUrl.toPercentEncoding(v)
                        for k, v in queryargs.items()
                    },
                })
            else:
                # pre v1.4 Picard did not support the queryargs kwargs
                del kwargs['queryargs']
                path = path + '?' + urlencode(queryargs)

        return super(PluginXmlWebService, self).get(
            host, port, path, handler, **kwargs
        )
