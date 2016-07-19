# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

import logging
import traceback
from PyQt4 import QtCore
from functools import partial

from picard.mbxml import medium_to_metadata, track_to_metadata
from picard.metadata import Metadata
from picard.track import Track

from . import settings
from .compat import urlencode, PluginXmlWebService
from .helpers.tags import apply_tag_weight, join_tags, strip_feat_artist
from .mixins import DebugMixin, CollectUnusedMixin
from .settings import translate_tag


# dictionary for query: toptag lists
CACHE = {}
# list of pending queries
PENDING = []

xmlws = PluginXmlWebService()
log = logging.getLogger(__name__)


# inherit from QObject to gain access to tagger, logger and config
class TaggerBase(DebugMixin, QtCore.QObject):
    def __init__(self, album, metadata, release_node):
        super(TaggerBase, self).__init__()

        # use this to write metatags
        self.metadata = metadata

        # load the tracks in this album locally
        if release_node is not None:
            self._load_tracks(release_node, album)

        # structure for storing raw toptag data
        self.toptags = dict(
            artist=[],
            album=[],
            track=[],
            all_track=[],
            all_artist=[],
        )

    def _load_tracks(self, release_node, album):
        # this happens after the album metadata processor in picard
        self.tracks = []
        for medium_node in release_node.medium_list[0].medium:
            mm = Metadata()
            mm.copy(album._new_metadata)
            medium_to_metadata(medium_node, mm)
            for track_node in medium_node.track_list[0].track:
                track = Track(track_node.recording[0].id, album)
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


    def filter_and_set_metadata(self, scope, all_tags, stats=False):
        """
        processing of a merged toptag list:
        handles disabled categories, sorting into categories,
        determines and enforces score threshold, assigns result to metatags
        optionally logs toptag statistics
        """
        result = {}
        for category in settings.CATEGORIES:
            # initialize empty list, unless exists because of an overflow
            result[category.name] = result.get(category.name, [])

            # this category is disabled
            if not category.is_enabled:
                continue

            filtered_tags = category.filter_tags(all_tags)
            # use extend, because of how overflow works,
            # directly writing to results
            result[category.name].extend(filtered_tags[:category.limit])
            overflow = filtered_tags[category.limit:]

            # if an overflow is configured, put the toptags, that exceed the
            # limit in the category configured for overflow
            if category.overflow and overflow:
                # the overflowed toptags are not considered in the threshold
                # calculation of that category, they are put directly into
                # the result list.
                log.info("%s: overflow (and scale by %s) to %s: %s",
                    category, str(category.overflow_scale), category.overflow,
                    ', '.join(['{} ({})'.format(t, s*category.overflow_scale) for t, s in overflow])
                        or 'None'
                )
                if overflow:
                    result[category.overflow] = [(t, s*category.overflow_scale) for t, s in overflow]

            # if a prepend-category is configured copy the tags from that
            # category in front of this one
            #TODO this works only "downstream" eg from grouping to genre, not the other way round
            if category.prepend:
                log.info('%s: prepending (and scale by %s) from %s: %s',
                    category, str(category.prepend_scale), category.prepend,
                    ', '.join(['{} ({})'.format(t, s*category.prepend_scale) for t, s in result[category.prepend]]) or 'None'
                )
                #actually do the prepend with scaling
                result[category.name] = [(t, s*category.prepend_scale) for t, s in result[category.prepend]] + result[category.name]

            #re-sort by score before providing to join_tags
            #using apply_tag_weight with scaling of 1.0 as a sorting function
            result[category.name] = apply_tag_weight((result[category.name], 1.0))

            #show final tags
            log.info('Final tags before making choice:')
            log.info(result[category.name])

            # category is done, assign tags to metadata
            metatag = category.get_metatag(scope)
            log.info('%s: metatag: %s', category, metatag)
            # some categories aren't valid for all scopes (eg occasion in album)
            if metatag is not None:
                self.metadata[metatag] = join_tags(
                    result[category.name],
                    limit=category.limit,
                    separator=category.separator,
                    sort=category.sort,
                    apply_titlecase=category.titlecase
                ) or settings.DEFAULT_UNKNOWN
                log.info("%s = %s", metatag, self.metadata[metatag])

    def process_album_tags(self):
        """
        this is called after all last.fm data is received to process the
        collected data for album tags.
        """
        log.info(">>> process album tags")
        if settings.DEBUG_STATS_ALBUM:
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

        self.filter_and_set_metadata(
            'album',
            all_tags,
            stats=settings.DEBUG_STATS_ALBUM
        )

    def process_track_tags(self):
        """
        this is called after all last.fm data is received to process the
        collected data for track tags.
        """
        log.info(">>> process track tags")
        if settings.DEBUG_STATS_TRACK:
            self.print_toptag_stats('track', 'track')
            self.print_toptag_stats('track', 'artist')

        # get complete, balanced, sorted list (high first) of tags
        all_tags = apply_tag_weight(
            (self.toptags['artist'],
             settings.CONFIG['track']['weight']['artist']),
            (self.toptags['track'], settings.CONFIG['track']['weight']['track'])
        )

        self.filter_and_set_metadata(
            'track',
            all_tags,
            stats=settings.DEBUG_STATS_TRACK
        )


class LastFmMixin(object):
    def __init__(self, album, metadata, release_node):
        super(LastFmMixin, self).__init__(album, metadata, release_node)

        # plugin internal requests counter, similar to the one in album
        # this is necessary to perform tasks before finalizing.
        # other plugins could have pending requests, so album_requests never
        # reaches zero in this plugin, but only later...
        self.requests = 0

        # finalizing is done on album level
        self.album = album

        # list of functions, that are called before finalizing the album data
        self.before_finalize = []

    def dispatch(self, tagtype, params):
        """
        Implements the caching mechanism.
        Lookup from cache or dispatch a new api request.
        """
        query = urlencode(params)
        # if the query is already cached only queue task
        if query in CACHE:
            log.debug("cached %s", query)
            self.add_task(partial(self.handle_cached_toptags, tagtype, query))
        # queries in the PENDING list are already queued, queue them like
        # cache tasks. by the time they will be processed, the actual query
        # will have stored data in the cache
        elif query in PENDING:
            log.debug("pending %s", query)
            self.add_task(partial(self.handle_cached_toptags, tagtype, query))
        # new queries are queued as http-requests
        else:
            log.debug("request %s", query)
            self.add_request(partial(self.handle_toptags, tagtype), params)

    def add_request(self, handler, params):
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
        query = urlencode(params)
        PENDING.append(query)

        # count requests, so that the album is not finalized until
        # the handler has been executed
        self.album._requests += 1
        self.requests += 1

        # queue http get request
        xmlws.get(
            settings.LASTFM_HOST,
            settings.LASTFM_PORT,
            settings.LASTFM_PATH,
             # wrap the handler in the finished decorator
            self.finished(handler),
            queryargs=params,
            priority=True,
            important=False,
        )

    def add_task(self, handler):
        """
        Use the webservice queue to add a task -- a simple function.
        """
        # count requests
        self.album._requests += 1
        self.requests += 1

        # queue function call
        xmlws.add_task(
            # wrap the handler in the finished decorator
            self.finished(handler),
            settings.LASTFM_HOST,
            settings.LASTFM_PORT,
            priority=False,
            important=False,
        )

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
            log.info("FIN")
            self.album._finalize_loading(None)

    def finished(self, func):
        """
        Decorator for wrapping a request handler function for tail call of
        `finish_request()`.
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

    def request_artist_toptags(self):
        """
        request toptags of an artist (via artist or albumartist)
        """
        artist = self.metadata["artist"]
        if artist:
            if settings.ENABLE_IGNORE_FEAT_ARTISTS:
                artist = strip_feat_artist(artist)
        else:
            artist = self.metadata["albumartist"]

        params = dict(
            method="artist.gettoptags",
            artist=artist,
            api_key=settings.LASTFM_KEY)
        self.dispatch("artist", params)

    def request_track_toptags(self):
        """
        request toptags of a track (via title, artist)
        """
        artist = self.metadata["artist"]
        if settings.ENABLE_IGNORE_FEAT_ARTISTS:
            artist = strip_feat_artist(artist)

        params = dict(
            method="track.gettoptags",
            track=self.metadata["title"],
            artist=artist,
            api_key=settings.LASTFM_KEY)
        self.dispatch("track", params)

    def request_album_toptags(self):
        """
        request toptags of an album (via album, albumartist)
        """
        params = dict(
            method="album.gettoptags",
            album=self.metadata["album"],
            artist=self.metadata["albumartist"],
            api_key=settings.LASTFM_KEY)
        self.dispatch("album", params)

    def request_all_track_toptags(self):
        """
        request toptags of all tracks in the album (via title, artist)
        """
        for track in self.tracks:
            artist = track.metadata["artist"]
            if settings.ENABLE_IGNORE_FEAT_ARTISTS:
                artist = strip_feat_artist(artist)

            params = dict(
                method="track.gettoptags",
                track=track.metadata["title"],
                artist=artist,
                api_key=settings.LASTFM_KEY)
            self.dispatch("all_track", params)

    def request_all_artist_toptags(self):
        """
        request toptags of all artists in the album (via artist)
        """
        for track in self.tracks:
            artist = track.metadata["artist"]
            if settings.ENABLE_IGNORE_FEAT_ARTISTS:
                artist = strip_feat_artist(artist)

            params = dict(
                method="artist.gettoptags",
                artist=artist,
                api_key=settings.LASTFM_KEY)
            self.dispatch("all_artist", params)

    def handle_toptags(self, tagtype, data, http, error):
        """
        Response handler for the last.fm webservice

        Performs the following steps:
          - read toptags from xml response
          - tag names are in lower case
          - tags with score below score_threshold are ignored
          - extends self.toptags with an unsorted list of (name, score) tuples
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
                log.warning("lfm api error: {0} - {1}".format(
                    error.attribs['code'], error.text))
                log.warning(str(http.url()))
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
            log.warning("no tags: %s, %s", tagtype, query)
            pass

    def handle_cached_toptags(self, tagtype, query):
        """
        Copy toptags from module-global cache to local toptags list.
        """
        toptags = CACHE.get(query, None)
        if toptags is not None:
            self.toptags[tagtype].extend(toptags)
        else:
            log.warning("cache error: %s, %s", tagtype, query)
            # TODO sometimes, the response from the http request is too slow,
            # so the queue is already processing "pending" cache requests,
            # while the response is not yet processed. the whole "pending"
            # design is flawed! workaround is refreshing :P


class LastFMTagger(CollectUnusedMixin, LastFmMixin, TaggerBase):
    def process_album_tags(self):
        super(LastFMTagger, self).process_album_tags()
        if settings.ENABLE_COLLECT_UNUSED:
            self.collect_unused()

    def process_track_tags(self):
        super(LastFMTagger, self).process_track_tags()
        if settings.ENABLE_COLLECT_UNUSED:
            self.collect_unused()
