# -*- coding: utf-8 -*-
import operator
import re

from .. import settings
from ..vendor.titlecase import titlecase


def uniq(iterable):
    """
    Make an iterable unique, preserving the order, returns a list
    http://code.activestate.com/recipes/52560/
    """
    set = {}
    return [set.setdefault(e, e) for e in iterable if e not in set]


def abbreviations(word, **kwargs):
    if word.upper() in settings.ABBREVIATIONS:
        return word.upper()


def join_tags(tuples, limit=None, separator=", ", sort=True, apply_titlecase=True):
    """
    create a metatag string for a list of tag tuples
    tag names are title-cased (override using titlecase)
    tags are sorted alphabetically (override using sort)
    tags are joined together using ", " (override using separator)
    if separator is None, tags are not joined, but a list is returned
    """
    # first limit to only the top ones...
    if limit:
        tuples = tuples[:limit]
    # then sort alphabetically
    if sort:
        tuples = sorted(tuples, key=operator.itemgetter(0), reverse=False)
    # fix case or not.
    if apply_titlecase:
        rv = [
            titlecase(tag, callback=abbreviations)
            for (tag, score) in tuples
        ]
    else:
        rv = [tag for (tag, score) in tuples]
    # remove duplicates, that we might have gotten from overflow
    rv = uniq(rv)
    if separator is None:
        return rv
    return separator.join(rv)


def apply_tag_weight(*args):
    """
    accepts a list of tuples.
    each tuple contains as first element a list of tag-tuples (name, score)
    and as second a weight factor.
    returns a list of tag-tuples, sorted by score (high first).
    """
    rv = {}
    for tags, weight in args:
        for name, score in tags:
            score = score * weight
            rv[name] = score + rv.get(name, 0)
    tuples = sorted(rv.items(), key=operator.itemgetter(1), reverse=True)
    return tuples


def strip_feat_artist(artist):
    match = re.match(r"([\s\S]+) feat.([\s\S]+)", artist, re.IGNORECASE)
    if match:
        return match.group(1)
    return artist
