# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import time

from picard.webservice import XmlWebService, REQUEST_DELAY


class PluginXmlWebService(XmlWebService):
    def _run_next_task(self):
        delay = sys.maxint
        for key in self._hosts:
            queue = self._high_priority_queues.get(key) or \
                    self._low_priority_queues.get(key)
            if not queue:
                continue
            now = time.time()
            last = self._last_request_times.get(key)
            request_delay = REQUEST_DELAY[key]
            last_ms = (now - last) * 1000 \
                if last is not None \
                else request_delay
            if last_ms >= request_delay:
                self.log.debug("Last request to %s was %d ms ago, "
                               "starting another one",
                    key, last_ms)
                # no delay before next task. it will be caught anyway, if it
                # is too soon. that way non-http-request tasks can be executed
                # without any delay with the same queue-key.
                d = 10
                queue.popleft()()
            else:
                d = request_delay - last_ms
                self.log.debug("Waiting %d ms before starting "
                               "another request to %s",
                    d, key)
            if d < delay:
                delay = d
        if delay < sys.maxint:
            self._timer.start(delay)
