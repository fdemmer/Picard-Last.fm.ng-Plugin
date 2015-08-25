# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import traceback
from functools import partial

from PyQt4 import QtCore

from picard.const import USER_DIR
from picard.mbxml import medium_to_metadata, track_to_metadata
from picard.metadata import Metadata
from picard.track import Track

from . import settings
from .helpers.qt import qt_urlencode
from .helpers.tags import apply_tag_weight, join_tags
from .helpers.webservice import PluginXmlWebService
from .settings import translate_tag


# dictionary for query: toptag lists
CACHE = {}
# list of pending queries
PENDING = []

xmlws = PluginXmlWebService()


class DebugMixin(object):
    def print_toplist(self, merged):
        def p(score):
            return int(float(score) / float(topscore) * 100.0)

        try:
            topscore = merged[0][1]
            toplist = ["{0}: {1} ({2}%)".format(n, s, p(s)) for n, s in
                       merged[:10]]
            self.log.info("{0}".format(", ".join(toplist)))
        except:
            self.log.info("None")

    def print_toptag_stats(self, scope, name, correction=1):
        toptags = self.toptags[name]
        weight = settings.CONFIG[scope]['weight'][name]
        self.log.info(
            "got {0} {1} tags (x{2}):".format(len(toptags), name, weight))
        merged = apply_tag_weight((toptags, correction))[:10]
        self.print_toplist(merged)


# inherit from QObject to gain access to tagger, logger and config
class LastFM(DebugMixin, QtCore.QObject):
    def __init__(self, album, metadata, release_node):
        super(LastFM, self).__init__()
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
                self._track_to_metadata(track_node, track)
                track._customize_metadata()

    def _track_to_metadata(self, track_node, track):
        # that's pretty ugly, but v1.2 requires the config argument
        # as it seems it was removed in v1.3
        try:
            track_to_metadata(track_node, track)
        except TypeError:
            # noinspection PyArgumentList
            track_to_metadata(track_node, track, self.config)

    def add_request(self, handler, query):
        """
        queue a data fetch request. this increases the requests counter.
        this method returns after queueing. the requests are then processed
        sequentially. queueing can be influenced using the priority and
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
        xmlws.get(
            settings.LASTFM_HOST, settings.LASTFM_PORT,
            path, handler,
            priority=True, important=False
        )

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
        xmlws.add_task(
            handler,
            settings.LASTFM_HOST, settings.LASTFM_PORT,
            priority=False, important=False
        )

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
        p = ["{0}={1}".format(k, qt_urlencode(v)) for (k, v) in params.items()]
        return '&'.join(p)

    def request_artist_toptags(self):
        """request toptags of an artist (via artist or albumartist)"""
        params = dict(
            method="artist.gettoptags",
            artist=self.metadata["artist"] or self.metadata["albumartist"],
            api_key=settings.API_KEY)
        query = self._get_query(params)
        self.cached_or_request("artist", query)

    def request_album_toptags(self):
        """request toptags of an album (via album, albumartist)"""
        params = dict(
            method="album.gettoptags",
            album=self.metadata["album"],
            artist=self.metadata["albumartist"],
            api_key=settings.API_KEY)
        query = self._get_query(params)
        self.cached_or_request("album", query)

    def request_track_toptags(self):
        """request toptags of a track (via title, artist)"""
        params = dict(
            method="track.gettoptags",
            track=self.metadata["title"],
            artist=self.metadata["artist"],
            api_key=settings.API_KEY)
        query = self._get_query(params)
        self.cached_or_request("track", query)

    def request_all_track_toptags(self):
        """request toptags of all tracks in the album (via title, artist)"""
        for track in self.tracks:
            params = dict(
                method="track.gettoptags",
                track=track.metadata["title"],
                artist=track.metadata["artist"],
                api_key=settings.API_KEY)
            query = self._get_query(params)
            self.cached_or_request("all_track", query)

    def request_all_artist_toptags(self):
        """
        request toptags of all artists in the album (via artist)
        """
        for track in self.tracks:
            params = dict(
                method="artist.gettoptags",
                artist=track.metadata["artist"],
                api_key=settings.API_KEY)
            query = self._get_query(params)
            self.cached_or_request("all_artist", query)

    def finish_request(self):
        """
        has to be called after/at the end of a request handler. reduces the
        pending requests counter and calls the finalize function if there is
        no open request left.
        """
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
        """
        Decorator for wrapping a request handler function.
        """

        def decorate(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except:
                self.album.tagger.log.error(
                    "Problem in handler:\n%s", traceback.format_exc())
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
            self.log.warning("no tags: {0}, {1}".format(tagtype, query))
            pass

    def handle_cached_toptags(self, tagtype, query):
        """Copy toptags from module-global cache to local toptags list."""
        toptags = CACHE.get(query, None)
        if toptags is not None:
            self.toptags[tagtype].extend(toptags)
        else:
            self.log.warning("cache error: {0}, {1}".format(tagtype, query))
            # TODO sometimes, the response from the http request is too slow,
            # so the queue is already processing "pending" cache requests,
            # while the response is not yet processed. the whole "pending"
            # design is flawed! workaround is refreshing :P


    def collect_unused(self):
        """
        This collects toptags not used to tag files.
        It is a way to find new genres/groupings in the tags used on last.fm.
        """
        self.log.debug(u"collecting unused toptags...")
        all_tags = apply_tag_weight(
            (self.toptags['album'], 1),
            (self.toptags['track'], 1),
            (self.toptags['artist'], 1),
            (self.toptags['all_track'], 1),
            (self.toptags['all_artist'], 1)
        )

        searchlists = [opt['searchlist'] for cat, opt in
                       settings.CATEGORIES.items()]
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
                CREATE TABLE toptags (tag TEXT PRIMARY KEY, score INTEGER)
                """)
        except:
            pass

        for tag, score in unknown_toptags:
            c.execute("""
                REPLACE INTO toptags (tag, score)
                VALUES (?,
                coalesce((SELECT score FROM toptags WHERE tag = ?),0)+?)
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
        for category, opt in settings.CATEGORIES.items():
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
                    score_threshold = int(float(score) * opt['threshold'])

                # store the toptag
                result[category].append((tag, score))

            if stats:
                self.log.info(
                    "> category {0} ({1}):".format(category, opt['limit']))
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
            metatag = settings.CONFIG[scope]['tags'].get(category, None)
            if metatag is not None:
                self.metadata[metatag] = join_tags(result[category],
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
        if settings.config.getboolean('global', 'print_tag_stats_album') and \
                settings.config.getboolean('global', 'print_tag_stats'):
            self.print_toptag_stats('album', 'album', len(self.tracks))
            self.print_toptag_stats('album', 'all_artist')
            self.print_toptag_stats('album', 'all_track')

        # get complete, balanced, sorted list (high first) of tags
        all_tags = apply_tag_weight(
            # album tag score gets multiplied by the total number of tracks
            # in the release to even out weight of all_* tags before merger
            (self.toptags['album'],
             settings.CONFIG['album']['weight']['album'] * len(self.tracks)),
            (self.toptags['all_track'],
             settings.CONFIG['album']['weight']['all_track']),
            (self.toptags['all_artist'],
             settings.CONFIG['album']['weight']['all_artist'])
        )

        self.filter_and_set_metadata('album', all_tags,
            stats=settings.config.getboolean('global', 'print_tag_stats_album'))
        if settings.config.getboolean('global', 'collect_unused'):
            self.collect_unused()

    def process_track_tags(self):
        """
        this is called after all last.fm data is received to process the
        collected data for track tags.
        """
        self.log.info(">>> process track tags")
        if settings.config.getboolean('global', 'print_tag_stats_track') and \
                settings.config.getboolean('global', 'print_tag_stats'):
            self.print_toptag_stats('track', 'track')
            self.print_toptag_stats('track', 'artist')

        # get complete, balanced, sorted list (high first) of tags
        all_tags = apply_tag_weight(
            (self.toptags['artist'],
             settings.CONFIG['track']['weight']['artist']),
            (self.toptags['track'], settings.CONFIG['track']['weight']['track'])
        )

        self.filter_and_set_metadata('track', all_tags,
            stats=settings.config.getboolean('global', 'print_tag_stats_track'))
        if settings.config.getboolean('global', 'collect_unused'):
            self.collect_unused()
