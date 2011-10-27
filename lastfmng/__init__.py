# -*- coding: utf-8 -*-

"""
Last.fm.ng plugin

"""

PLUGIN_NAME = "Last.fm.ng"
PLUGIN_AUTHOR = "Florian Demmer"
PLUGIN_DESCRIPTION = "reimagination of the popular last.fm plus plugin"
PLUGIN_VERSION = "0.2"
PLUGIN_API_VERSIONS = ["0.15"]

from PyQt4 import QtGui, QtCore
from picard.metadata import register_track_metadata_processor
from picard.metadata import register_album_metadata_processor
#from picard.script import register_script_function
#from picard.ui.options import register_options_page, OptionsPage
#from picard.config import BoolOption, IntOption, TextOption
#from picard.plugins.lastfmplus.ui_options_lastfm import Ui_LastfmOptionsPage
from picard.util import partial

import traceback
import operator
import sys
#import urllib
import urlparse
import time

from helper import *

LASTFM_HOST = "ws.audioscrobbler.com"
LASTFM_PORT = 80
API_KEY = "b25b959554ed76058ac220b7b2e0a026"

# From http://www.last.fm/api/tos, 2011-07-30
# 4.4 (...) You will not make more than 5 requests per originating IP address
# per second, averaged over a 5 minute period, without prior written consent.
from picard.webservice import REQUEST_DELAY
REQUEST_DELAY[(LASTFM_HOST, LASTFM_PORT)] = 200

CACHE = {}
PENDING = []

#FAKE_HOST = "localhost"
#FAKE_PORT = "0"
#REQUEST_DELAY[(FAKE_HOST, FAKE_PORT)] = 1

# the genres defined in id3v1 incl. the winamp extensions
GENRE_ID3V1 = ["Blues", "Classic Rock", "Country", "Dance", "Disco", "Funk", 
    "Grunge", "Hip-Hop", "Jazz", "Metal", "New Age", "Oldies", "Other", "Pop",
    "R&B", "Rap", "Reggae", "Rock", "Techno", "Industrial", "Alternative",
    "Ska", "Death Metal", "Pranks", "Soundtrack", "Euro-Techno", "Ambient",
    "Trip-Hop", "Vocal", "Jazz+Funk", "Fusion", "Trance", "Classical",
    "Instrumental", "Acid", "House", "Game", "Sound Clip", "Gospel", "Noise",
    "Alternative Rock", "Bass", "Soul", "Punk", "Space", "Meditative",
    "Instrumental Pop", "Instrumental Rock", "Ethnic", "Gothic", "Darkwave",
    "Techno-Industrial", "Electronic", "Pop-Folk", "Eurodance", "Dream",
    "Southern Rock", "Comedy", "Cult", "Gangsta", "Top 40", "Christian Rap",
    "Pop/Funk", "Jungle", "Native US", "Cabaret", "New Wave", "Psychadelic",
    "Rave", "Showtunes", "Trailer", "Lo-Fi", "Tribal", "Acid Punk", "Acid Jazz",
    "Polka", "Retro", "Musical", "Rock & Roll", "Hard Rock", "Folk",
    "Folk-Rock", "National Folk", "Swing", "Fast Fusion", "Bebob", "Latin",
    "Revival", "Celtic", "Bluegrass", "Avantgarde", "Gothic Rock", 
    "Progressive Rock", "Psychedelic Rock", "Symphonic Rock", "Slow Rock", 
    "Big Band", "Chorus", "Easy Listening", "Acoustic", "Humour", "Speech",
    "Chanson", "Opera", "Chamber Music", "Sonata", "Symphony", "Booty Bass",
    "Primus", "Porn Groove", "Satire", "Slow Jam", "Club", "Tango", "Samba",
    "Folklore", "Ballad", "Power Ballad", "Rhytmic Soul", "Freestyle", "Duet",
    "Punk Rock", "Drum Solo", "Acapella", "Euro-House", "Dance Hall", "Goa",
    "Drum & Bass", "Club-House", "Hardcore", "Terror", "Indie", "BritPop",
    "Negerpunk", "Polsk Punk", "Beat", "Christian Gangsta Rap", "Heavy Metal",
    "Black Metal", "Crossover", "Contemporary Christian", "Christian Rock",
    "Merengue", "Salsa", "Trash Metal", "Anime", "Jpop", "Synthpop"]
DEFAULT_FILTER_MAJOR = GENRE_ID3V1
#DEFAULT_FILTER_MAJOR = ("audiobooks, blues, classic rock, classical, country, "
#    "dance, electronica, folk, hip-hop, indie, jazz, kids, metal, pop, punk, "
#    "reggae, rock, soul, trance")

DEFAULT_FILTER_MINOR = ("2 tone, a cappella, abstract hip-hop, acid, acid jazz,"
    "acid rock, acoustic, acoustic guitar, acoustic rock, adult alternative,"
    "adult contemporary, alternative, alternative country, alternative folk,"
    "alternative metal, alternative pop, alternative rock, ambient, anti-folk,"
    "art rock, atmospheric, aussie hip-hop, avant-garde, ballads, baroque, beach,"
    "beats, bebop, big band, blaxploitation, blue-eyed soul, bluegrass, blues"
    "rock, boogie rock, boogie woogie, bossa nova, breakbeat, breaks, brit pop,"
    "brit rock, british invasion, broadway, bubblegum pop, cabaret, calypso, cha"
    "cha, choral, christian rock, classic country, classical guitar, club,"
    "college rock, composers, contemporary country, contemporary folk, country"
    "folk, country pop, country rock, crossover, dance pop, dancehall, dark"
    "ambient, darkwave, delta blues, dirty south, disco, doo wop, doom metal,"
    "downtempo, dream pop, drum and bass, dub, dub reggae, dubstep, east coast"
    "rap, easy listening, electric blues, electro, electro pop, elevator music,"
    "emo, emocore, ethnic, eurodance, europop, experimental, fingerstyle, folk"
    "jazz, folk pop, folk punk, folk rock, folksongs, free jazz, french rap,"
    "funk, funk metal, funk rock, fusion, g-funk, gaelic, gangsta rap, garage,"
    "garage rock, glam rock, goa trance, gospel, gothic, gothic metal, gothic"
    "rock, gregorian, groove, grunge, guitar, happy hardcore, hard rock,"
    "hardcore, hardcore punk, hardcore rap, hardstyle, heavy metal, honky tonk,"
    "horror punk, house, humour, hymn, idm, indie folk, indie pop, indie rock,"
    "industrial, industrial metal, industrial rock, instrumental, instrumental"
    "hip-hop, instrumental rock, j-pop, j-rock, jangle pop, jazz fusion, jazz"
    "vocal, jungle, latin, latin jazz, latin pop, lounge, lovers rock, lullaby,"
    "madchester, mambo, medieval, melodic rock, minimal, modern country, modern"
    "rock, mood music, motown, neo-soul, new age, new romantic, new wave, noise,"
    "northern soul, nu metal, old school rap, opera, orchestral, philly soul,"
    "piano, political reggae, polka, pop life, pop punk, pop rock, pop soul, post"
    "punk, post rock, power pop, progressive, progressive rock, psychedelic,"
    "psychedelic folk, psychedelic punk, psychedelic rock, psychobilly,"
    "psytrance, punk rock, quiet storm, r&b, ragga, rap, rap metal, reggae pop,"
    "reggae rock, rock and roll, rock opera, rockabilly, rocksteady, roots, roots"
    "reggae, rumba, salsa, samba, screamo, shock rock, shoegaze, ska, ska punk,"
    "smooth jazz, soft rock, southern rock, space rock, spoken word, standards,"
    "stoner rock, surf rock, swamp rock, swing, symphonic metal, symphonic rock,"
    "synth pop, tango, techno, teen pop, thrash metal, traditional country,"
    "traditional folk, tribal, trip-hop, turntablism, underground, underground"
    "hip-hop, underground rap, urban, vocal trance, waltz, west coast rap,"
    "western swing, world, world fusion, power metal")
DEFAULT_FILTER_COUNTRY = ("african, american, arabic, australian, austrian, "
    "belgian, brazilian, british, canadian, caribbean, celtic, chinese, cuban,"
    "danish, dutch, eastern europe, egyptian, estonian, european, finnish,"
    "french, german, greek, hawaiian, ibiza, icelandic, indian, iranian, irish,"
    "island, israeli, italian, jamaican, japanese, korean, mexican, middle"
    "eastern, new zealand, norwegian, oriental, polish, portuguese, russian,"
    "scandinavian, scottish, southern, spanish, swedish, swiss, thai, third"
    "world, turkish, welsh, western")
DEFAULT_FILTER_CITY = ("acapulco, adelaide, amsterdam, athens, atlanta, "
    "atlantic city, auckland, austin, bakersfield, bali, baltimore, bangalore,"
    "bangkok, barcelona, barrie, beijing, belfast, berlin, birmingham, bogota,"
    "bombay, boston, brasilia, brisbane, bristol, brooklyn, brussels, bucharest,"
    "budapest, buenos aires, buffalo, calcutta, calgary, california, cancun,"
    "caracas, charlotte, chicago, cincinnati, cleveland, copenhagen, dallas,"
    "delhi, denver, detroit, dublin, east coast, edmonton, frankfurt, geneva,"
    "glasgow, grand rapids, guadalajara, halifax, hamburg, hamilton, helsinki,"
    "hong kong, houston, illinois, indianapolis, istanbul, jacksonville, kansas"
    "city, kiev, las vegas, leeds, lisbon, liverpool, london, los angeles,"
    "louisville, madrid, manchester, manila, marseille, mazatlan, melbourne,"
    "memphis, mexico city, miami, michigan, milan, minneapolis, minnesota,"
    "mississippi, monterrey, montreal, munich, myrtle beach, nashville, new"
    "jersey, new orleans, new york, new york city, niagara falls, omaha, orlando,"
    "oslo, ottawa, palm springs, paris, pennsylvania, perth, philadelphia,"
    "phoenix, phuket, pittsburgh, portland, puebla, raleigh, reno, richmond, rio"
    "de janeiro, rome, sacramento, salt lake city, san antonio, san diego, san"
    "francisco, san jose, santiago, sao paulo, seattle, seoul, shanghai,"
    "sheffield, spokane, stockholm, sydney, taipei, tampa, texas, tijuana, tokyo,"
    "toledo, toronto, tucson, tulsa, vancouver, victoria, vienna, warsaw,"
    "wellington, westcoast, windsor, winnipeg, zurich")
DEFAULT_FILTER_MOOD = ("angry, bewildered, bouncy, calm, cheerful, chill, cold,"
    "complacent, crazy, crushed, cynical, depressed, dramatic, dreamy, drunk,"
    "eclectic, emotional, energetic, envious, feel good, flirty, funky, groovy,"
    "happy, haunting, healing, high, hopeful, hot, humorous, inspiring, intense,"
    "irritated, laidback, lonely, lovesongs, meditation, melancholic, melancholy,"
    "mellow, moody, morose, passionate, peace, peaceful, playful, pleased,"
    "positive, quirky, reflective, rejected, relaxed, retro, sad, sentimental,"
    "sexy, silly, smooth, soulful, spiritual, suicidal, surprised, sympathetic,"
    "trippy, upbeat, uplifting, weird, wild, yearning")
DEFAULT_FILTER_OCCASION = ("background, birthday, breakup, carnival, chillout, "
    "christmas, death, dinner, drinking, driving, graduation, halloween, hanging"
    "out, heartache, holiday, late night, love, new year, party, protest, rain,"
    "rave, romantic, sleep, spring, summer, sunny, twilight, valentine, wake up,"
    "wedding, winter, work")
DEFAULT_FILTER_CATEGORY = ("animal songs, attitude, autumn, b-side, ballad, "
    "banjo, bass, beautiful, body parts, bootlegs, brass, cafe del mar, chamber"
    "music, clarinet, classic, classic tunes, compilations, covers, cowbell,"
    "deceased, demos, divas, dj, drugs, drums, duets, field recordings, female,"
    "female vocalists, film score, flute, food, genius, girl group, great lyrics,"
    "guitar solo, guitarist, handclaps, harmonica, historical, horns, hypnotic,"
    "influential, insane, jam, keyboard, legends, life, linedance, live, loved,"
    "lyricism, male, male vocalists, masterpiece, melodic, memories, musicals,"
    "nostalgia, novelty, number songs, old school, oldie, oldies, one hit"
    "wonders, orchestra, organ, parody, poetry, political, promos, radio"
    "programs, rastafarian, remix, samples, satire, saxophone, showtunes,"
    "sing-alongs, singer-songwriter, slide guitar, solo instrumentals, songs with"
    "names, soundtracks, speeches, stories, strings, stylish, synth, title is a"
    "full sentence, top 40, traditional, trumpet, unique, unplugged, violin,"
    "virtuoso, vocalization, vocals")

TRANSLATIONS = {
    "drum 'n' bass": u"drum and bass",
    "drum n bass": u"drum and bass",
    "trip hop": u"trip-hop",
    "Melancholic": u"Melancholy",
}

CONFIG = {
    # on album level set the following metadata
    'album': {
        'weight': dict(album=2, all_artist=4, all_track=4),
        'tags': {
            # category  metatag
            'genre':    'albumgenre',
            'grouping': 'albumgrouping',
            'mood':     'albummood',
        }
    },
    # for each track set the following metadata
    'track': {
        'weight': dict(artist=2, track=8),
        'tags': {
            # category  metatag
            'genre':    'genre',
            'grouping': 'grouping',
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

# the official id3 genre tags
LFM_GENRE = ListChecker(DEFAULT_FILTER_MAJOR)
# a more specific genre grouping
LFM_GROUPING = StringChecker(DEFAULT_FILTER_MINOR, ",")
# eg. angry, cheerful, clam, ...
LFM_MOOD = StringChecker(DEFAULT_FILTER_MOOD, ",")
# country names
LFM_COUNTRY = StringChecker(DEFAULT_FILTER_COUNTRY, ",")
# city names
LFM_CITY = StringChecker(DEFAULT_FILTER_CITY, ",")
# musical era, eg. 80s, 90s, ...
LFM_DECADE = RegexChecker("^([1-9][0-9])*[0-9]0s$")
# the full year, eg. 1995, 2000, ...
LFM_YEAR = RegexChecker("^[1-9][0-9]{3}$")
# eg. background, late night, party
LFM_OCCASION = StringChecker(DEFAULT_FILTER_OCCASION, ",")
# i don't really know
LFM_CATEGORY = StringChecker(DEFAULT_FILTER_CATEGORY, ",")

CATEGORIES = {
    'genre': dict(searchlist=LFM_GENRE, enabled=True, 
        limit=1, sort=True,  titlecase=True, separator=", ", unknown="Unknown"),
    'grouping': dict(searchlist=LFM_GROUPING, enabled=True, 
        limit=3, sort=False, titlecase=True, separator=", ", unknown="Unknown"),
    'mood': dict(searchlist=LFM_MOOD, enabled=True, 
        limit=4, sort=False, titlecase=True, separator=", ", unknown="Unknown"),
    'occasion': dict(searchlist=LFM_OCCASION, enabled=True, 
        limit=4, sort=False, titlecase=True, separator=", ", unknown="Unknown"),
    'category': dict(searchlist=LFM_CATEGORY, enabled=True, 
        limit=4, sort=False, titlecase=True, separator=", ", unknown="Unknown"),
    'country': dict(searchlist=LFM_COUNTRY, enabled=True, 
        limit=1, sort=True,  titlecase=True, separator=", ", unknown="Unknown"),
    'city': dict(searchlist=LFM_CITY, enabled=True, 
        limit=1, sort=True,  titlecase=True, separator=", ", unknown="Unknown"),
    'decade': dict(searchlist=LFM_DECADE, enabled=True, 
        limit=1, sort=True,  titlecase=False, separator=", ", unknown="Unknown"),
    'year': dict(searchlist=LFM_YEAR, enabled=False, 
        limit=1, sort=True,  titlecase=False, separator=", ", unknown="Unknown"),
}


# inherit from QObject to gain access to tagger, logger and config
class LastFM(QtCore.QObject):
    def __init__(self, album, metadata):
        # finalizing is done on album level
        self.album = album
        # the tracks in this album. shoudl be used read only!
        self.tracks = album._new_tracks
        # album_metadata is always the album metadata, ...
        #self.album_metadata = album._new_metadata
        # while metadata can be album or track meta
        # use this to write metatags
        self.metadata = metadata
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

    def add_request(self, handler, query):
        """
        queue a data fetch request. this increases the requests counter.
        this method returns after queueing. the requests are then processed 
        sequencially. queueing can be influenced using the priority and 
        important switches.
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
        self.tagger.xmlws.get(LASTFM_HOST, LASTFM_PORT, 
            path, handler, priority=True, important=False)

    def add_task(self, handler):
        """
        use the webservice queue to add a task, a simple function
        """
        # count requests
        self.album._requests += 1
        self.requests += 1
        
        # wrap the handler in the finished decorator
        handler = self.finished(handler)
        # queue function call
        self.tagger.xmlws.add_task(handler, 
            LASTFM_HOST, LASTFM_PORT, priority=False, important=False)


    def cached_or_request(self, tagtype, query):
        if query in CACHE:
            #print "cached {}".format(query)
            self.add_task(partial(self.handle_cached_toptags, tagtype, query))
        elif query in PENDING:
            #print "pending {}".format(query)
            self.add_task(partial(self.handle_cached_toptags, tagtype, query))
        else:
            #print "request {}".format(query)
            self.add_request(partial(self.handle_toptags, tagtype), query)


    def _get_query(self, params):
        """build query from kwargs"""
        p = ["{}={}".format(k, encode_str(v)) for (k, v) in params.items()]
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
        #print "finish request: {}".format(self.requests)
        self.album._requests -= 1
        self.requests -= 1
        if self.requests == 0:
            # this was the last request in this plugin, work with the data
            for func in self.before_finalize:
                func()
        if self.album._requests == 0:
            # this was the last request in general, finalize metadata
            self.album._finalize_loading(None)

    def finished(self, func):
        """decorator for wrapping a request handler function"""
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
        score_threshold = 1
        # cache key
        query = str(http.url().encodedQuery())
        # temp storage for toptags
        tmp = []

        try:
            lfm = data.lfm.pop()

            if lfm.attribs['status'] == 'failed':
                error = lfm.error.pop()
                self.log.warning("lfm api error: {} - {}".format(
                    error.attribs['code'], error.text))
                self.log.warning(str(http.url()))
                return

            toptags = lfm.toptags.pop()
            for tag in toptags.tag:
                name = tag.name[0].text.strip().lower()
                # replace toptag name with a translation
                name = TRANSLATIONS.get(name, name)
                # scores are integers from 0 to 100, 
                # but it is not a percentage per tagtype 
                # (so the sum of all scores is > 100)
                score = int(tag.count[0].text.strip())
                # only store above score_threshold
                if score >= score_threshold:
                    tmp.append((name, score))

            # add the result of this run to the cache
            CACHE[query] = tmp

            # extend "global" toptags list with the ones from this run
            self.toptags[tagtype].extend(tmp)

        except AttributeError:
            #sys.exc_info()
            #print http.url()
            #print data
            self.log.warning("no tags: {}, {}".format(tagtype, query))
            pass

    def handle_cached_toptags(self, tagtype, query):
        """copies toptags from cache to apropritate local storage"""
        #print "cached"
        toptags = CACHE.get(query, None)
        if toptags is not None:
            self.toptags[tagtype].extend(toptags)
        else:
            self.log.warning("cache error: {}, {}".format(tagtype, query))


    def process_album_tags(self):
        """
        this is called after all last.fm data is received to process the 
        collected data for album tags.
        """
        self.log.debug("process album tags")
        self.log.debug("got {} album tags".format(len(self.toptags['album'])))
        self.log.debug("got {} all_track tags".format(len(self.toptags['all_track'])))
        self.log.debug("got {} all_artist tags".format(len(self.toptags['all_artist'])))

        # get complete, balanced, sorted list (high first) of tags
        all_tags = merge_tags(
            # album tag score gets multiplied by the total number of tracks 
            # in the release to even out weight of all_* tags before merger
            (self.toptags['album'], CONFIG['album']['weight']['album']*len(self.tracks)), 
            (self.toptags['all_track'], CONFIG['album']['weight']['all_track']), 
            (self.toptags['all_artist'], CONFIG['album']['weight']['all_artist'])
        )

        #TODO refactor this whole block
        # find valid tags, split into categories and limit results
        result = {}
        for category, opt in CATEGORIES.items():
            result[category] = []

            # this category is disabled
            if not opt['enabled']:
                continue

            for tag, score in all_tags:
                # ignore tags not in this category
                if tag not in opt['searchlist']:
                    continue
                # limit the number of tags in this category
                if len(result[category]) >= opt['limit']:
                    continue
                result[category].append((tag, score))

            # category is done, assign toptags to metadata
            metatag = CONFIG['album']['tags'].get(category, None)
            if metatag is not None:
                self.metadata[metatag] = tag_string(result[category],
                    sort=opt['sort'], titlecase=opt['titlecase'], 
                    separator=opt['separator']) or opt['unknown']

        #print self.metadata

    def process_track_tags(self):
        """
        this is called after all last.fm data is received to process the 
        collected data for track tags.
        """
        self.log.debug("process track tags")
        self.log.debug("got {} track tags".format(len(self.toptags['track'])))
        self.log.debug("got {} artist tags".format(len(self.toptags['artist'])))

        # get complete, balanced, sorted list (high first) of tags
        all_tags = merge_tags(
            (self.toptags['artist'], CONFIG['track']['weight']['artist']), 
            (self.toptags['track'], CONFIG['track']['weight']['track'])
        )

        # find valid tags, split into categories and limit results
        result = {}
        for category, opt in CATEGORIES.items():
            result[category] = []

            # this category is disabled
            if not opt['enabled']:
                continue

            for tag, score in all_tags:
                # ignore tags not in this category
                if tag not in opt['searchlist']:
                    continue
                # limit the number of tags in this category
                if len(result[category]) >= opt['limit']:
                    continue
                result[category].append((tag, score))

            # category is done, assign toptags to metadata
            metatag = CONFIG['track']['tags'].get(category, None)
            if metatag is not None:
                self.metadata[metatag] = tag_string(result[category],
                    sort=opt['sort'], titlecase=opt['titlecase'], 
                    separator=opt['separator']) or opt['unknown']

        #print self.metadata

def encode_str(s):
    # Yes, that's right, Last.fm prefers double URL-encoding
    s = s.encode('utf-8')
    #s = urllib.quote(s).lower()
    #return urllib.quote(urllib.quote(s)).lower()
    s = QtCore.QUrl.toPercentEncoding(s)
    #s = QtCore.QUrl.toPercentEncoding(unicode(s))
    return s

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

def tag_string(tuples, separator=", ", titlecase=True, sort=True):
    """
    create a metatag string for a list of tag tuples
    tag names are title-cased (override using titlecase)
    tags are sorted alphabetically (override using sort)
    tags are joined together using ", " (override using separator)
    """
    if sort:
        tuples = sorted(tuples, key=operator.itemgetter(0), reverse=False)
    if titlecase:
        return separator.join([tag.title() for (tag, score) in tuples])
    return separator.join([tag for (tag, score) in tuples])



@register_track_metadata_processor
def track_metadata_processor(album, metadata, track_node, release_node):
    """
    determine track metadata using track and artist last.fm tags
    """
    lfmws = LastFM(album, metadata)
    lfmws.before_finalize.append(lfmws.process_track_tags)

    lfmws.request_track_toptags()
    lfmws.request_artist_toptags()

@register_album_metadata_processor
def album_metadata_processor(album, metadata, release_node):
    """
    determine album metadata using album and all artist and all track last.fm 
    tags in the album.
    """
    lfmws = LastFM(album, metadata)
    lfmws.before_finalize.append(lfmws.process_album_tags)

    lfmws.request_album_toptags()
    lfmws.request_all_track_toptags()
    lfmws.request_all_artist_toptags()


