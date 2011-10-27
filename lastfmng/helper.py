
import re

class ListChecker:
    """
    create a list-like tag checker from a list of strings.
    strings can be in any case and whitespace is stripped.
    """
    def __init__(self, values):
        self.values = [value.lower().strip() for value in values]
    
    def __contains__(self, value):
        return value.lower().strip() in self.values

    def __repr__(self):
        return "<{}([{}, ...])>".format(self.__class__.__name__, 
            ", ".join(self.values[:3]))

class StringChecker(ListChecker):
    """create a list-like tag checker from a string with a certain separator"""
    def __init__(self, string, separator=","):
        ListChecker.__init__(self, string.split(separator))

class RegexChecker:
    """
    use a regular expression to check tags for validity instead of a list
    with the same "interface": the in comparator
    """
    def __init__(self, regexp):
        self.regexp = re.compile(regexp)
    
    def __contains__(self, value):
        return self.regexp.match(value)

    def __repr__(self):
        return "<{}('{}')>".format(self.__class__.__name__, 
            self.regexp.pattern)

