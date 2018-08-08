# -*- coding: utf-8 -*-
import codecs
import os

from picard import log
from picard.webservice import ratecontrol
from .helpers.searchlists import RegexpSearchlist, StringSearchlist
from .vendor.configparser import ConfigParser, NoOptionError

config_files = [
    'defaults.ini',
    'config.ini',
    'lastfm.ini',
]


def load_config(filenames):
    cfg = None
    for filename in filenames:
        cfg = load_config_file(filename, cfg)
    return cfg


def load_config_file(filename, cfg=None):
    if not cfg:
        cfg = ConfigParser()
    try:
        full_path = os.path.join(os.path.dirname(__file__), filename)
        with codecs.open(full_path, 'r', 'utf8') as fh:
            cfg.read_file(fh)
    except IOError:
        pass
    return cfg


def get_config(section, name, dtype=''):
    try:
        return getattr(config, 'get{}'.format(dtype))(section, name)
    except NoOptionError:
        pass


config = load_config(config_files)


LASTFM_HOST = config.get('global', 'lastfm_host')
LASTFM_PORT = config.getint('global', 'lastfm_port')
LASTFM_KEY = config.get('global', 'lastfm_key')
LASTFM_PATH = '/2.0/'
log.info('host: %s:%s', LASTFM_HOST, LASTFM_PORT)
log.info('key: %s', LASTFM_KEY)


ENABLE_COLLECT_UNUSED = config.getboolean('global', 'collect_unused')
log.info('collect_unused: %s', ENABLE_COLLECT_UNUSED)
ENABLE_IGNORE_FEAT_ARTISTS = config.getboolean('global', 'ignore_feat_artists')
log.info('ignore_feat_artists: %s', ENABLE_IGNORE_FEAT_ARTISTS)
DEFAULT_UNKNOWN = config.get('global', 'default_unknown').strip()
log.info('default_unknown: %s', DEFAULT_UNKNOWN)

# list of abbreviations for titlecase
ABBREVIATIONS = config.get('searchlist', 'abbreviations')


DEBUG_STATS = config.getboolean('global', 'print_tag_stats')
DEBUG_STATS_TRACK = config.getboolean('global', 'print_tag_stats_track') \
    if DEBUG_STATS else False
DEBUG_STATS_ALBUM = config.getboolean('global', 'print_tag_stats_album') \
    if DEBUG_STATS else False


# toptag to metatag configuration
CONFIG = {
    # on album level set the following metadata
    'album': {
        # multiplication factors for each type of toptag
        'weight': dict(album=15, all_artist=55, all_track=30),
    },
    # for each track set the following metadata
    'track': {
        # TODO *plus supports disabling toptag types per metatag... eg. country only via artist toptags.
        'weight': dict(artist=2, track=8),
    }
}


class Category(object):
    def __init__(self, name, searchlist=None):
        self.name = name
        self.searchlist = self.load_searchlist(searchlist)

    def __str__(self):
        return self.name

    @property
    def is_enabled(self):
        return self.category_config('enabled', 'boolean', True)

    @property
    def threshold(self):
        return self.category_config('threshold', 'float', 0.5)

    @property
    def limit(self):
        return self.category_config('limit', 'int', 4)

    @property
    def prepend(self):
        return self.category_config('prepend')

    @property
    def overflow(self):
        return self.category_config('overflow')

    @property
    def sort(self):
        return self.category_config('sort', 'boolean', False)

    @property
    def titlecase(self):
        return self.category_config('titlecase', 'boolean', True)

    @property
    def separator(self):
        value = self.category_config('separator')
        return value.strip('"') if value else None

    def get_metatag(self, scope):
        """
        Return the metatag to assign the category result to.
        """
        assert scope in ('album', 'track')
        return self.category_config('metatag_{}'.format(scope))

    def category_config(self, key, dtype='', default=None):
        value = get_config('category-{}'.format(self.name), key, dtype)
        if value is None:
            value = get_config('category-{}'.format('defaults'), key, dtype)
        if value is None:
            value = default
        return value

    def load_searchlist(self, searchlist=None):
        # none given: create searchlist according to config
        if not searchlist:
            regexp = self.category_config('regexp')
            words = get_config('searchlist', self.name)

            # load regexp from category config
            if regexp:
                searchlist = RegexpSearchlist(regexp)
            # use words for string search list
            elif words:
                searchlist = StringSearchlist(words)

        # exclude 'soundtrack' as a tag
        if get_config('global', 'soundtrack_is_no_genre', 'boolean'):
            searchlist.add_exclude('soundtrack')

        return searchlist

    def _get_threshold(self, tags):
        threshold = max([score for tag, score in tags]) * self.threshold
        log.info(
            '%s: score threshold: %s (%.0f%%)',
            self, threshold, self.threshold * 100
        )
        return threshold

    def _filter_by_searchlist(self, tags):
        """
        Exclude tags not relevant for this category.
        """
        return [
            (tag, score)
            for tag, score in tags
            if tag in self.searchlist
        ]

    def _filter_by_threshold(self, tags):
        """
        Exclude tags below the threshold.

        The threshold is meant to remove tags that are extremely rare
        compared to the most popular one. When there are only very few tags
        in a category even a very seldom used tag would be considered
        otherwise.

        For example:
          assume we allow 2 tags in the 'decade' category
          found tags are: '90s' with score 900 and '70s' with score 200
          ... so somebody probably tagged this '70s' by mistake
          ... with a configured threshold of 0.5 any tag with score less
              than 450 would not be considered
        """
        threshold = self._get_threshold(tags)
        return [
            (tag, score) for tag, score in tags
            if score >= threshold
        ]

    def filter_tags(self, all_tags):
        # exclude tags not relevant for this category
        tags = self._filter_by_searchlist(all_tags)

        # exclude tags below the threshold
        if tags:
            self._log_tags(tags, 'before threshold filter')
            tags = self._filter_by_threshold(tags)
            self._log_tags(tags, 'filtered')
        else:
            log.info('%s: no tags', self)

        return tags

    def _log_tags(self, tags, message, limit=5):
        log.info('%s: %s tag(s) %s:', self, len(tags), message)
        log.info(
            '%s: %s%s',
            self,
            ', '.join(['{} ({})'.format(t, s) for t, s in tags][:limit]),
            ', ...' if len(tags) > limit else '',
        )


CATEGORIES = [
    # grouping is used as major/high level category
    Category('grouping'),
    Category('genre'),
    # eg. angry, cheerful, clam, ...
    Category('mood'),
    # eg. background, late night, party
    Category('occasion'),
    # i don't really know
    Category('category'),
    # country names
    Category('country'),
    # city names
    Category('city'),
    # musical era, eg. 80s, 90s, ...
    Category('decade'),
    # the full year, eg. 1995, 2000, ...
    Category('year'),
]
log.info('enabled categories: %s', ', '.join([
    '{} ({})'.format(c.name, c.limit)
    for c
    in CATEGORIES
    if c.is_enabled is True
]))


# From http://www.last.fm/api/tos, 2011-07-30
# 4.4 (...) You will not make more than 5 requests per originating IP address
# per second, averaged over a 5 minute period, without prior written consent.
ratecontrol.set_minimum_delay((LASTFM_HOST, LASTFM_PORT), 200)


def translate_tag(name):
    try:
        name = config.get('translations', name.lower())
    except NoOptionError:
        pass
    return name
