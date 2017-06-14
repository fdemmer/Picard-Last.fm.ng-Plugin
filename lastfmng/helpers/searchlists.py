# -*- coding: utf-8 -*-
import re


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
        # TODO add wildcard matching
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
        return "<{}([{}, ...])>".format(
            self.__class__.__name__,
            ", ".join(self.include[:3])
        )

    def add_exclude(self, name):
        """
        add a single tag name to the exclude list
        """
        self.exclude.append(name.lower().strip())


class StringSearchlist(ListSearchlist):
    """
    create a list-like tag checker from a string with a certain separator
    """
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
        return "<{}('{}')>".format(
            self.__class__.__name__,
            self.regexp.pattern
        )
