
import re
import sys
import time

from PyQt4 import QtCore, QtNetwork
from PyQt4.QtCore import QUrl

from picard.webservice import XmlWebService
from picard.webservice import REQUEST_DELAY


class ListSearchlist:
    """
    create a list-like tag checker from a list of strings.
    strings can be in any case and whitespace is stripped.
    """
    def __init__(self, include=None, exclude=None):
        self.include = [value.lower().strip() for value in include or []]
        self.exclude = exclude or []
    
    def match(self, value):
        """
        return True if the value is found in the include list of tag names,
        override to change the matching
        """
        #TODO add wildcard matching
        return value.lower().strip() in self.include

    def __contains__(self, value):
        """
        return True if the value is found in the include list of tag names,
        return False if the value is in the exclude list or not in include
        this is the interface used in toptag categorizing
        """
        if value.lower() in self.exclude:
            return None
        return self.match(value)

    def __repr__(self):
        return "<{}([{}, ...])>".format(self.__class__.__name__, 
            ", ".join(self.include[:3]))

    def remove(self, name):
        """add a single tag name to the exclude list"""
        self.exclude.append(name.lower().strip())

class StringSearchlist(ListSearchlist):
    """create a list-like tag checker from a string with a certain separator"""
    def __init__(self, string, separator=","):
        ListSearchlist.__init__(self, string.split(separator))


class RegexpSearchlist(ListSearchlist):
    """
    use a regular expression to check tags for validity instead of a list
    with the same "interface": the in comparator
    """
    def __init__(self, regexp):
        ListSearchlist.__init__(self, None)
        self.regexp = re.compile(regexp)

    def match(self, value):
        return self.regexp.match(value)

    def __repr__(self):
        return "<{}('{}')>".format(self.__class__.__name__, 
            self.regexp.pattern)


class SearchTree(dict):
    def __init__(self, trunk, branches):
        #TODO add lowercase-ing to all tags
        self.trunk = trunk
        dict.__init__(self, branches)

    def get_searchlist(self, result):
        try:
            toptags = result.get(self.trunk, None)
            toptag_name = toptags[0][0].lower()
            return self.get(toptag_name, None)
        except:
            return None


class PluginXmlWebService(XmlWebService):
    def _run_next_task(self):
        delay = sys.maxint
        for key in self._hosts:
            queue = self._high_priority_queues.get(key) or self._low_priority_queues.get(key)
            if not queue:
                continue
            now = time.time()
            last = self._last_request_times.get(key)
            request_delay = REQUEST_DELAY[key]
            last_ms = (now - last) * 1000 if last is not None else request_delay
            if last_ms >= request_delay:
                self.log.debug("Last request to %s was %d ms ago, starting another one", key, last_ms)
                # no delay before next task. it will be caught anyway, if it 
                # is too soon. that way non-http-request tasks can be executed 
                # without any delay with the same queue-key.
                d = 10
                queue.popleft()()
            else:
                d = request_delay - last_ms
                self.log.debug("Waiting %d ms before starting another request to %s", d, key)
            if d < delay:
                delay = d
        if delay < sys.maxint:
            self._timer.start(delay)

