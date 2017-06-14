# -*- coding: utf-8 -*-
"""
Script functions
----------------

This module contains additional script functions required by or recommended
to be used with the plugin.

Script functions need to be registered in __init__.py!
"""


def func_set2(parser, name, value):
    """Adds ``value`` to the variable ``name``."""
    if value:
        if name.startswith("_"):
            name = "~" + name[1:]
        _ = parser.context[name].split(';')
        _.append(value)
        parser.context[name] = _
    return ""
