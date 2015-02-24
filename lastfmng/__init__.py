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

PLUGIN_NAME = "Last.fm.ng"
PLUGIN_AUTHOR = "Florian Demmer"
PLUGIN_DESCRIPTION = "reimagination of the popular last.fm plus plugin"
PLUGIN_LICENSE = "GPL-3.0"
PLUGIN_LICENSE_URL = "http://opensource.org/licenses/GPL-3.0"
PLUGIN_VERSION = "0.7.3"
PLUGIN_API_VERSIONS = ["0.15"]

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
except:
    from .odict import OrderedDict

from .ConfigParser import ConfigParser
from .helper import *


config_file = os.path.join(os.path.dirname(__file__), "config.ini")
config = ConfigParser()
config.readfp(open(config_file))

LASTFM_HOST = "ws.audioscrobbler.com"
LASTFM_PORT = 80
API_KEY = "0a8b8f968b285654f9b4f16e8e33f2ee"

# From http://www.last.fm/api/tos, 2011-07-30
# 4.4 (...) You will not make more than 5 requests per originating IP address
# per second, averaged over a 5 minute period, without prior written consent.
from picard.webservice import REQUEST_DELAY
REQUEST_DELAY[(LASTFM_HOST, LASTFM_PORT)] = 200

# dictionary for query: toptag lists
CACHE = {}
# list of pending queries
PENDING = []


# toptag to metatag configuration
CONFIG = {
    # on album level set the following metadata
    'album': {
        # multiplication factors for each type of toptag
        'weight': dict(album=15, all_artist=55, all_track=30),
        'tags': {
            # category  metatag
            'grouping': 'albumgrouping',
            'genre':    'albumgenre',
            'mood':     'albummood',
        }
    },
    # for each track set the following metadata
    'track': {
        #TODO *plus supports disabling toptag types per metatag... eg. country only via artist toptags.
        'weight': dict(artist=2, track=8),
        'tags': {
            # category  metatag
            'grouping': 'grouping',
            'genre':    'genre',
            'mood':     'mood',
            'year':     'year',
            'occasion': 'comment:Songs-DB_Occasion',
            'decade':   'comment:Songs-DB_Custom1',
            'category': 'comment:Songs-DB_Custom2',
            'city':     'comment:Songs-DB_Custom3',
            'country':  'comment:Songs-DB_Custom4',
        }
    }
}


# a searchtree allows setting tags depending on a reference category's toptag
# the other category must have been already processed! (it must come before 
# the category using the searchtree in the CATEGORIES configuration)
# set the reference category's name as the "trunk" value
# the "branches" are the tags allowed (the searchlist) for a specific toptag
# eg. a "genre" tree:
# trunk=grouping, and a track's most popular "grouping" toptag is "folk", 
# then the value of the "folk" branch is used as searchlist for the "genre" 
# category
# in case no suitable branch is available, the normal searchlist is used!
EXAMPLE_GENRE_TREE = SearchTree(
    # set the tree trunk to the reference category's name
    trunk='grouping',
    # configure searchlists per toptag in the reference category
    # only the most popular toptag in a category is used
    # everything must be lower case!
    branches={
        # only use tags from the list in case the 
        "folk": ["finnish folk", "traditional folk"],
        "rock": RegexpSearchlist("^.*rock.*$"),
        "electronic": ["jazz"],
        "pop": RegexpSearchlist("^.*pop.*$"),
    })


#TODO integrate CONFIG stuff into this dict
CATEGORIES = OrderedDict([
    # grouping is used as major/high level category
    ('grouping', dict(
        # limit: a hard limit for how many toptags are assigned to the metatag
        # threshold: percentage; only the toptags with a score above are used
        # enabled: don't collect toptags for that category
        # sort: alphabetically sort toptags before joining to string
        # titlecase: apply titlecase() function to each toptag
        # separator: used to join toptags if >1 are to be used (None to use multtag)
        # unknown: the string to use if no toptag was found for the category
        # overflow: name of another category, unused toptags in this category 
        #     will be used in the given one.
        searchlist=StringSearchlist(config.get('searchlist', 'major_genre')),
        limit=1, threshold=0.5, enabled=True, sort=False, titlecase=True,
        separator=", ", unknown="Unknown", overflow='genre')),
    # allow genre toptags from a searchtree and use the searchlsit as fallback
    ('genre', dict(
        searchlist=StringSearchlist(config.get('searchlist', 'minor_genre')),
        #searchtree=EXAMPLE_GENRE_TREE, 
        limit=4, threshold=0.5, enabled=True, sort=False, titlecase=True,
        separator=None, unknown="Unknown")),
    # eg. angry, cheerful, clam, ...
    ('mood', dict(
        searchlist=StringSearchlist(config.get('searchlist', 'mood')),
        limit=4, threshold=0.5, enabled=True, sort=False, titlecase=True,
        separator=None, unknown="Unknown")),
    # eg. background, late night, party
    ('occasion', dict(
        searchlist=StringSearchlist(config.get('searchlist', 'occasion')),
        limit=4, threshold=0.5, enabled=True, sort=False, titlecase=True,
        separator=None, unknown="Unknown")),
    # i don't really know
    ('category', dict(
        searchlist=StringSearchlist(config.get('searchlist', 'category')),
        limit=4, threshold=0.5, enabled=True, sort=False, titlecase=True,
        separator=None, unknown="Unknown")),
    # country names
    ('country', dict(
        searchlist=StringSearchlist(config.get('searchlist', 'country')),
        limit=2, threshold=0.7, enabled=True, sort=True, titlecase=True,
        separator=None, unknown="Unknown")),
    # city names
    ('city', dict(
        searchlist=StringSearchlist(config.get('searchlist', 'city')),
        limit=1, threshold=0.7, enabled=True, sort=True, titlecase=True,
        separator=None, unknown="Unknown")),
    # musical era, eg. 80s, 90s, ...
    ('decade', dict(
        searchlist=RegexpSearchlist("^([1-9][0-9])*[0-9]0s$"),
        limit=1, threshold=0.7, enabled=True, sort=True, titlecase=False,
        separator=", ", unknown="Unknown")),
    # the full year, eg. 1995, 2000, ...
    ('year', dict(
        searchlist=RegexpSearchlist("^[1-9][0-9]{3}$"),
        limit=1, threshold=0.7, enabled=False, sort=True, titlecase=False,
        separator=", ", unknown="Unknown")),
])

if config.getboolean('global', 'soundtrack_is_no_genre'):
    CATEGORIES['grouping']['searchlist'].remove('soundtrack')
    CATEGORIES['genre']['searchlist'].remove('soundtrack')


xmlws = PluginXmlWebService()


# inherit from QObject to gain access to tagger, logger and config
class LastFM(QtCore.QObject):
    def __init__(self, album, metadata, release_node):
        # finalizing is done on album level
        self.album = album
        # use this to write metatags
        self.metadata = metadata
        # load the tracks in this album locally
        if release_node is not None:
            self._load_tracks(release_node)
        # list of functions, that are called before finalizing the album data
        self.before_finalize = []
        # plugin internal requests counter, similar to the one in album
        # this is necessary to perform tasks before finalizing.
        # other plugins could have pending requests, so album_requests never 
        # reaches zero in this plugin, but only later...
        self.requests = 0
        # structure for storing raw toptag data
        self.toptags = dict(artist=[], album=[], track=[],
            all_track=[], all_artist=[])

    def _load_tracks(self, release_node):
        # this happens after the album metadata processor in picard
        self.tracks = []
        for medium_node in release_node.medium_list[0].medium:
            mm = Metadata()
            mm.copy(self.album._new_metadata)
            medium_to_metadata(medium_node, mm)
            for track_node in medium_node.track_list[0].track:
                track = Track(track_node.recording[0].id, self.album)
                self.tracks.append(track)
                # Get track metadata
                tm = track.metadata
                tm.copy(mm)
                # thats pretty ugly, but v1.2 requires the config argument
                # as it seems it was removed in v1.3
                try:
                    track_to_metadata(track_node, track)
                except TypeError:
                    track_to_metadata(track_node, track, self.config)
                track._customize_metadata()

    def add_request(self, handler, query):
        """
        queue a data fetch request. this increases the requests counter.
        this method returns after queueing. the requests are then processed 
        sequencially. queueing can be influenced using the priority and 
        important switches.
        by using priority here and not in add_task, all requests will be 
        executed before the tasks, if they use the same HOST,PORT tuple for 
        queueing.
        the handlers are called with the responses. the next request is only 
        started after the previous' request handler has returned.
        handlers are wrapped with the finished function to reduce the requests
        counter and finalize the album data.
        """
        # add query to list of pending requests, no request should be sent twice
        PENDING.append(query)
        # build scrobbler api 2.0 url
        path = "/2.0/?" + query
        # count requests, so that the album is not finalized until 
        # the handler has been executed
        self.album._requests += 1
        self.requests += 1

        # wrap the handler in the finished decorator
        handler = self.finished(handler)
        # queue http get request
        xmlws.get(LASTFM_HOST, LASTFM_PORT,
            path, handler, priority=True, important=False)

    def add_task(self, handler):
        """
        Use the webservice queue to add a task -- a simple function.
        """
        # count requests
        self.album._requests += 1
        self.requests += 1

        # wrap the handler in the finished decorator
        handler = self.finished(handler)
        # queue function call
        xmlws.add_task(handler,
            LASTFM_HOST, LASTFM_PORT, priority=False, important=False)


    def cached_or_request(self, tagtype, query):
        # if the query is already cached only queue task
        if query in CACHE:
            self.log.debug("cached {0}".format(query))
            self.add_task(partial(self.handle_cached_toptags, tagtype, query))
        # queries in the PENDING list are already queued, queue them like
        # cache tasks. by the time they will be processed, the actual query 
        # will have stored data in the cache
        elif query in PENDING:
            self.log.debug("pending {0}".format(query))
            self.add_task(partial(self.handle_cached_toptags, tagtype, query))
        # new queries are queued as http-requests
        else:
            self.log.debug("request {0}".format(query))
            self.add_request(partial(self.handle_toptags, tagtype), query)


    def _get_query(self, params):
        """Build and return a query string from the given params dictionary."""
        p = ["{0}={1}".format(k, encode_str(v)) for (k, v) in params.items()]
        return '&'.join(p)

    def request_artist_toptags(self):
        """request toptags of an artist (via artist or albumartist)"""
        params = dict(
            method="artist.gettoptags",
            artist=self.metadata["artist"] or self.metadata["albumartist"],
            api_key=API_KEY)
        query = self._get_query(params)
        self.cached_or_request("artist", query)

    def request_album_toptags(self):
        """request toptags of an album (via album, albumartist)"""
        params = dict(
            method="album.gettoptags",
            album=self.metadata["album"],
            artist=self.metadata["albumartist"],
            api_key=API_KEY)
        query = self._get_query(params)
        self.cached_or_request("album", query)

    def request_track_toptags(self):
        """request toptags of a track (via title, artist)"""
        params = dict(
            method="track.gettoptags",
            track=self.metadata["title"],
            artist=self.metadata["artist"],
            api_key=API_KEY)
        query = self._get_query(params)
        self.cached_or_request("track", query)

    def request_all_track_toptags(self):
        """request toptags of all tracks in the album (via title, artist)"""
        for track in self.tracks:
            params = dict(
                method="track.gettoptags",
                track=track.metadata["title"],
                artist=track.metadata["artist"],
                api_key=API_KEY)
            query = self._get_query(params)
            self.cached_or_request("all_track", query)

    def request_all_artist_toptags(self):
        """request toptags of all artists in the album (via artist)"""
        for track in self.tracks:
            params = dict(
                method="artist.gettoptags",
                artist=track.metadata["artist"],
                api_key=API_KEY)
            query = self._get_query(params)
            self.cached_or_request("all_artist", query)


    def finish_request(self):
        """
        has to be called after/at the end of a request handler. reduces the
        pending requests counter and calls the finalize function if there is 
        no open request left.
        """
        #print "finish request: {0}".format(self.requests)
        self.album._requests -= 1
        self.requests -= 1
        if self.requests == 0:
            # this was the last request in this plugin, work with the data
            for func in self.before_finalize:
                func()
        if self.album._requests == 0:
            # this was the last request in general, finalize metadata
            self.log.info("FIN")
            self.album._finalize_loading(None)

    def finished(self, func):
        """Decorator for wrapping a request handler function."""
        def decorate(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except:
                self.album.tagger.log.error("Problem in handler: %s",
                    traceback.format_exc())
                raise
            finally:
                self.finish_request()
        return decorate


    def handle_toptags(self, tagtype, data, http, error):
        """
        request handler for the last.fm webservice

        read toptags from xml response.
        tag names are in lower case.
        tags with score below score_threshold are ignored.
        returns an unsorted list of tuples (name, score).
        """
        #print "new reply"
        score_threshold = 1
        # cache key
        query = str(http.url().encodedQuery())
        # temp storage for toptags
        tmp = []

        try:
            lfm = data.lfm.pop()

            if lfm.attribs['status'] == 'failed':
                error = lfm.error.pop()
                self.log.warning("lfm api error: {0} - {1}".format(
                    error.attribs['code'], error.text))
                self.log.warning(str(http.url()))
                return

            toptags = lfm.toptags.pop()
            for tag in toptags.tag:
                name = tag.name[0].text.strip().lower()
                # replace toptag name with a translation
                name = translate_tag(name)
                # scores are integers from 0 to 100, 
                # but it is not a percentage per tagtype 
                # (so the sum of all scores is > 100)
                score = int(tag.count[0].text.strip())
                # only store above score_threshold
                if score >= score_threshold:
                    tmp.append((name, score))

            # add the result of this run to the cache
            CACHE[query] = tmp

            # extend local toptags list with the ones from this run
            self.toptags[tagtype].extend(tmp)

        except AttributeError:
            #sys.exc_info()
            #print http.url()
            #print data
            self.log.warning("no tags: {0}, {1}".format(tagtype, query))
            pass

    def handle_cached_toptags(self, tagtype, query):
        """Copy toptags from module-global cache to local toptags list."""
        #print "cached"
        toptags = CACHE.get(query, None)
        if toptags is not None:
            self.toptags[tagtype].extend(toptags)
        else:
            self.log.warning("cache error: {0}, {1}".format(tagtype, query))
            #TODO sometimes, the response from the http request is too slow, 
            # so the queue is already processing "pending" cache requests, 
            # while the response is not yet processed. the whole "pending" 
            # design is flawed! workaround is refreshing :P

    def print_toplist(self, merged):
        def p(s):
            return int(float(s)/float(topscore)*100.0)
        try:
            topscore = merged[0][1]
            toplist = ["{0}: {1} ({2}%)".format(n, s, p(s)) for n, s in merged[:10]]
            self.log.info("{0}".format(", ".join(toplist)))
        except:
            self.log.info("None")

    def print_toptag_stats(self, scope, name, correction=1):
        toptags = self.toptags[name]
        weight = CONFIG[scope]['weight'][name]
        self.log.info("got {0} {1} tags (x{2}):".format(len(toptags), name, weight))
        merged = merge_tags((toptags, correction))[:10]
        self.print_toplist(merged)

    def collect_unused(self):
        """
        This collects toptags not used to tag files.
        It is a way to find new genres/groupings in the tags used on last.fm.
        """
        self.log.debug(u"collecting unused toptags...")
        all_tags = merge_tags(
            (self.toptags['album'], 1),
            (self.toptags['track'], 1),
            (self.toptags['artist'], 1),
            (self.toptags['all_track'], 1),
            (self.toptags['all_artist'], 1)
        )

        searchlists = [opt['searchlist'] for cat, opt in CATEGORIES.items()]
        unknown_toptags = []

        for toptag in all_tags:
            tag, score = toptag
            for searchlist in searchlists:
                if tag in searchlist:
                    toptag = None
                    break
            if toptag is not None:
                unknown_toptags.append(toptag)

        dbfile = os.path.join(USER_DIR, 'lastfmng', 'toptags.db')
        self.log.debug(u"opening database: %s", dbfile)

        import sqlite3
        conn = sqlite3.connect(dbfile)
        c = conn.cursor()

        try:
            c.execute("""
                create table toptags (tag text primary key, score integer)
                """)
        except:
            pass


        for tag, score in unknown_toptags:
            c.execute("""
                replace into toptags (tag, score)
                values (?,
                coalesce((select score from toptags where tag = ?),0)+?)
                """, (tag, tag, score))

        conn.commit()
        c.close()

    def filter_and_set_metadata(self, scope, all_tags, stats=False):
        """
        processing of a merged toptag list:
        handles disabled categories, sorting into categories, searchtree loading,
        determines and enforces score threshold, assigns result to metatags
        optionally logs toptag statistics
        """
        # find valid tags, split into categories and limit results
        if stats:
            self.log.info(">>> name: {0}".format(
                (self.metadata.get('title') or \
                self.metadata.get('album')).encode('utf-8')))

        result = {}
        for category, opt in CATEGORIES.items():
            # initialize empty list, unless exists because of an overflow
            result[category] = result.get(category, [])
            score_threshold = 0

            # this category is disabled
            if not opt['enabled']:
                continue

            # use a simple searchlist for the category
            searchlist = opt['searchlist']
            # if a searchtree is configured for this category...
            searchtree = opt.get('searchtree', None)
            if searchtree is not None:
                # get the searchlist from the tree-branch using the result
                # or fall back to the configured searchlist
                searchlist = searchtree.get_searchlist(result) or searchlist
            #print searchlist

            for tag, score in all_tags:

                # stop searching when tag score is below threshold
                # (they are sorted!)
                if score < score_threshold:
                    break

                # ignore tags not in this category
                if tag not in searchlist:
                    continue

                # first toptag in this category, calculate threshold
                if score_threshold == 0:
                    score_threshold = int(float(score)*opt['threshold'])

                # store the toptag
                result[category].append((tag, score))

            if stats:
                self.log.info("> category {0} ({1}):".format(category, opt['limit']))
                self.print_toplist(result[category])

            # if an overflow is configured, put the toptags, that exceed the 
            # limit in the category configured for overflow
            overflow = opt.get('overflow', None)
            if overflow is not None:
                # the overflowed toptags are not considered in the threshold
                # calculation of that category, they are put directly into
                # the result list.
                result[overflow] = result[category][opt['limit']:]
                if stats:
                    self.log.info("...overflow to {0}:".format(overflow))
                    self.print_toplist(result[overflow])

            # category is done, assign toptags to metadata
            metatag = CONFIG[scope]['tags'].get(category, None)
            if metatag is not None:
                self.metadata[metatag] = tag_string(result[category],
                    sort=opt['sort'], titlecase=opt['titlecase'],
                    limit=opt['limit'], separator=opt['separator']) or \
                    opt['unknown']

                self.log.info("%s = %s" % (metatag, self.metadata[metatag]))

    def process_album_tags(self):
        """
        this is called after all last.fm data is received to process the 
        collected data for album tags.
        """
        self.log.info(">>> process album tags")
        if config.getboolean('global', 'print_tag_stats_album') and \
            config.getboolean('global', 'print_tag_stats'):
            self.print_toptag_stats('album', 'album', len(self.tracks))
            self.print_toptag_stats('album', 'all_artist')
            self.print_toptag_stats('album', 'all_track')

        # get complete, balanced, sorted list (high first) of tags
        all_tags = merge_tags(
            # album tag score gets multiplied by the total number of tracks 
            # in the release to even out weight of all_* tags before merger
            (self.toptags['album'], CONFIG['album']['weight']['album']*len(self.tracks)),
            (self.toptags['all_track'], CONFIG['album']['weight']['all_track']),
            (self.toptags['all_artist'], CONFIG['album']['weight']['all_artist'])
        )
        #self.log.info("all_tags tags:")
        #self.print_toplist(all_tags)

        self.filter_and_set_metadata('album', all_tags,
            stats=config.getboolean('global', 'print_tag_stats_album'))
        if config.getboolean('global', 'collect_unused'):
            self.collect_unused()

    def process_track_tags(self):
        """
        this is called after all last.fm data is received to process the 
        collected data for track tags.
        """
        self.log.info(">>> process track tags")
        if config.getboolean('global', 'print_tag_stats_track') and \
            config.getboolean('global', 'print_tag_stats'):
            self.print_toptag_stats('track', 'track')
            self.print_toptag_stats('track', 'artist')

        # get complete, balanced, sorted list (high first) of tags
        all_tags = merge_tags(
            (self.toptags['artist'], CONFIG['track']['weight']['artist']),
            (self.toptags['track'], CONFIG['track']['weight']['track'])
        )
        #self.log.info("all_tags tags:")
        #self.print_toplist(all_tags)

        self.filter_and_set_metadata('track', all_tags,
            stats=config.getboolean('global', 'print_tag_stats_track'))
        if config.getboolean('global', 'collect_unused'):
            self.collect_unused()


def encode_str(s):
    return QtCore.QUrl.toPercentEncoding(s)

def uniq(alist):
    # http://code.activestate.com/recipes/52560/
    set = {}
    return [set.setdefault(e,e) for e in alist if e not in set]

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
            score = score*weight
            rv[name] = score+rv.get(name, 0)
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


def func_set2(parser, name, value):
    """Adds ``value`` to the variable ``name``."""
    if value:
        if name.startswith("_"):
            name = "~" + name[1:]
        _ = parser.context[name].split(';')
        _.append(value)
        parser.context[name] = _
    return ""
register_script_function(func_set2, "set2")

