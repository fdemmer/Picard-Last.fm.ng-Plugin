# -*- coding: utf-8 -*-
"""
Last.fm.ng plugin
-----------------

This plugin is supposed to be used with the following naming rules::

    $rreplace(%subdirectory%/%albumgrouping%/$if2(%albumartist%,%artist%) - $if($if2(%originalyear%,%originaldate%,%date%),$left($if2(%originalyear%,%originaldate%,%date%),4),0000) - $replace(%album%,...,…)/$replace(%album%,...,…) - $if($ne(1,%totaldiscs%),%discnumber%,)$num(%tracknumber%,2) - %artist% - %title%,[*|:"<>?],~)

It builds a basic directory structure using the `%subdirectory%` and
`%albumgrouping%` variables.

Set this script, to get the proper `%subdirectory%`::

$set(subdirectory,Archive Albums)
$if($eq(%releasetype%,soundtrack),
    $set(subdirectory,Archive Soundtracks)
    $set(genre,Soundtrack)
)
$if($eq(%releasetype%,compilation),
    $if($eq(%albumartist%,Various Artists),
        $set(subdirectory,Archive Compilations))
)

It puts all albums, that look like soundtracks or compilations in a different
top-level directory, than "normal" albums. Also it adds a tag called 
"Soundtrack" to all tracks that are soundtracks. Remove the `set2()` line
if you do not want that.

    The `set2()` script function is non-standard and included in the plugin!
    You may need to restart Picard after activating the plugin, to have it
    recognize the command.

The `%albumgrouping%` is determined per album by the plugin.

Unfortunately the album-plugin processor is not called for non-album tracks, so
you won't have an `%albumgrouping%` set. Use the following script to put those
in a separate directory without grouping-subdirectories::

    $if($eq(%album%,[non-album tracks]),$set(subdirectory,Archive Non-Album))

In addition to creating the basic directory structure, the naming rules create
the filename and album-directory with some character cleanup. The resulting
album-directory will consist of::

    %albumartist% or %artist%
    %originalyear% or %date% or "0000"
    %album% (with "..." replaced by "…")

The filenames will be::

    %album% (with "..." replaced by "…")
    %tracknumber% (prepended with %discnumber% if there is more than one)
    %artist%
    %title%

In addition the special characters `*|:"<>?` are replaced by `~` in the whole
string.
"""

from .meta import *


import os
import operator
import traceback

from picard.const import USER_DIR
from picard.mbxml import medium_to_metadata, track_to_metadata
from picard.metadata import Metadata
from picard.metadata import register_album_metadata_processor
from picard.metadata import register_track_metadata_processor
from picard.script import register_script_function
from picard.track import Track
from picard.util import partial


# import our implementation with older pythons
try:
    from collections import OrderedDict
except ImportError:
    from .odict import OrderedDict

from .ConfigParser import ConfigParser
from .helpers import *


def encode_str(s):
    return QtCore.QUrl.toPercentEncoding(s)


def uniq(alist):
    # http://code.activestate.com/recipes/52560/
    set = {}
    return [set.setdefault(e, e) for e in alist if e not in set]


def translate_tag(name):
    try:
        name = config.get('translations', name.lower())
    except:
        pass
    return name


def merge_tags(*args):
    """
    accepts a list of tuples.
    each tuple contains as first element a list of tag-tuples 
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


def tag_string(tuples, separator=", ", titlecase=True, sort=True, limit=None):
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
    if titlecase:
        rv = [tag.title() for (tag, score) in tuples]
    else:
        rv = [tag for (tag, score) in tuples]
    # remove duplicates
    #TODO this is only necessary because of the way overflow is implemented, not really clean :(
    rv = uniq(rv)
    if separator is None:
        return rv
    return separator.join(rv)


@register_track_metadata_processor
def track_metadata_processor(album, metadata, track_node, release_node):
    """
    Determine track metadata using track and artist last.fm tags
    """
    lfmws = LastFM(album, metadata, release_node)
    lfmws.before_finalize.append(lfmws.process_track_tags)

    lfmws.request_track_toptags()
    lfmws.request_artist_toptags()


@register_album_metadata_processor
def album_metadata_processor(album, metadata, release_node):
    """
    Determine album metadata using album and all artist and all track last.fm 
    tags in the album.    
    """
    lfmws = LastFM(album, metadata, release_node)
    lfmws.before_finalize.append(lfmws.process_album_tags)

    lfmws.request_album_toptags()
    lfmws.request_all_track_toptags()
    lfmws.request_all_artist_toptags()


register_script_function(func_set2, "set2")
