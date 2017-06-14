# -*- coding: utf-8 -*-
from PyQt5 import QtCore


def urlencode(params):
    return '&'.join([
        "{0}={1}".format(k, QtCore.QUrl.toPercentEncoding(v, b'', b''))
        for (k, v)
        in params.items()
    ])
