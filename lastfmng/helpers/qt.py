# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from PyQt4 import QtCore


def qt_urlencode(s):
    #TODO why not use the stdlib function?
    return QtCore.QUrl.toPercentEncoding(s)
