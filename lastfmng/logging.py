# -*- coding: utf-8 -*-
import logging

from picard import log as picard_log


class PicardHandler(logging.Handler):
    def emit(self, record):
        levels = {
            10: picard_log.LOG_DEBUG,
            20: picard_log.LOG_INFO,
            30: picard_log.LOG_WARNING,
            40: picard_log.LOG_ERROR,
            50: picard_log.LOG_ERROR,
        }
        level = levels.get(record.levelno, picard_log.LOG_DEBUG)
        message = '{} - {}'.format('Last.fm.ng', record.msg)
        picard_log.main_logger.message(level, message, *record.args)


def setup_logging():
    log = logging.getLogger()
    log.setLevel(0)
    log.addHandler(PicardHandler())
