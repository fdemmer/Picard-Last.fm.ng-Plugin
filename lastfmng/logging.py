# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import logging

from picard import log as picard_log


class PicardHandler(logging.NullHandler):
    def handle(self, record):
        levels = {
            10: picard_log.LOG_DEBUG,
            20: picard_log.LOG_INFO,
            30: picard_log.LOG_WARNING,
            40: picard_log.LOG_ERROR,
            50: picard_log.LOG_ERROR,
        }
        level = levels.get(record.levelno, picard_log.LOG_DEBUG)
        picard_log.main_logger.message(level, record.msg, *record.args)

    def emit(self, record):
        pass


def setup_logging():
    log = logging.getLogger()
    log.addHandler(PicardHandler())
