# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
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
from .plugin import LastFM
from .script import func_set2

from picard.metadata import register_album_metadata_processor
from picard.metadata import register_track_metadata_processor
from picard.script import register_script_function


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
