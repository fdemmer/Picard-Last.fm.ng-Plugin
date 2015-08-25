# -*- coding: utf-8 -*-
def func_set2(parser, name, value):
    """Adds ``value`` to the variable ``name``."""
    if value:
        if name.startswith("_"):
            name = "~" + name[1:]
        _ = parser.context[name].split(';')
        _.append(value)
        parser.context[name] = _
    return ""
