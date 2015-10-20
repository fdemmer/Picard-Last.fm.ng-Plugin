# Picard Last.fm.ng Plugin

## About

This is a rewrite of the Musicbrainz Picard Last.fm plugins.
Initial motivation was cleaner configuration and more predictable outcomes.
It also used the Last.fm API v2.0 from the start.

Thanks go out to everybody contributing to the original and plus Last.fm
plugins! They were invaluable as a starting point.

### Features

 - Last.fm API v2.0
 - "albumgrouping" and "albumgenre" metatags for per-album tagging/naming
 - save tags as multiple tags or combined to a string
 - optional: ignore featured artists when looking up tags


## Install

Download the latest release from the github [releases][0] page.

Extract the "lastfmng" directory in the archive to you local user's plugin 
directory:

 - Windows: ``%APPDATA%\MusicBrainz\Picard\plugins``
 - Linux/MacOS: ``~/.config/MusicBrainz/Picard/plugins``

Start or restart Picard to load the plugin and enable it in the options 
dialog for plugins.


## Updating

It is recommended to backup your ``config.ini`` and delete the existing
"lastfmng" directory before extracting a new version to the plugins directory.

Then copy the configuration file back in place.

Sorry for the inconvenience.


## Configuration

The plugin does not provide a configuration dialog, but is easy to configure
using ini-files.

The provided ``defaults.ini`` contains all available settings.

To customize settings is is recommended to create a new file called 
``config.ini`` for your settings. If available it will be loaded after 
the defaults overwriting the default values with your preferences.


### Last.fm

Please use your own Last.fm API key and set it using ``lastfm_key``.
You don't need to change ``lastfm_host`` or ``lastfm_port``, but by setting
``lastfm_port`` to ``443`` https will be used.

If you want you can put the Last.fm related settings in an extra file called 
``lastfm.ini``.


### Tags

The basic concept of the plugin is this:

1. Download "tags" for an album, artist and track. 
   A "tag" is just a word users have assigned it can be anything like 
   "my favourite", "heard last night", "sucks" or terms we are more interested 
   in like "classic", "80s" or "death metal".
2. Filter and separate all the "tags" into categories 
   (like "genre", "mood", "country", ...)
3. Sort the "tags" by popularity (the number of times used) in each category.
4. Assign the the most popular of each category to an actual "metatag" 
   (eg. the "genre" id3 tag)

The plugin uses a fixed list of categories:

 - grouping
 - genre
 - mood
 - occasion
 - category
 - country
 - city
 - decade
 - year


#### Searchlists

For the categories grouping, genre, mood, occasion, category, country and city
so called searchlists are used to find valid terms in the downloaded "tags".

Customize the lists in the ``[searchlist]`` section of the config file to add 
or remove valid terms.

Translations of common tag variations are set in the ``[translations]`` section.
The first value is replaced with the second one.


#### Category configuration

For each category there is a section in the config file. 

To disable using a specific category set ``enabled`` to False. 

If you set the ``limit`` to 1 and two "tags" have exactly the same popularity 
the result will be exactly one, which one however is not clearly defined! 
There is room for improvement here.

Setting ``sort`` to True will sort the "tags" alphabetically *after* the ones with the
highest popularity have been determined. Set this to False to keep the one with the
highest popularity in front (from left to right)!

Using ``titlecase`` you can switch fixing the case of toptags off and on. The
``separator`` is used to combine more than one toptag into a metatag string and in
case not a single toptag was found for a category the value of 
``default_unknown`` is set.


## How it works

This plugin works via two Picard plugin API triggers:

- register_track_metadata_processor
- register_album_metadata_processor


### Album metadata processor

In the "album" run the plugin collects the toptags for 

- the album ("album" list), 
- the artist of each track  ("all_artists" list) and 
- each track ("all_tracks" list). 

The toptags are collected in lists and when all tags are received, they are
sorted into "categories" using the search lists. The "weight" parameters in the 
CONFIG dictionary are the factors, that are applied to the "score" of each tag.

So use the "weight" parameters to influence, whether to rank the toptags from 
eg. the album higher, than those of all tracks combined.

The "tag" parameters define in what metatag (id3, ...) the toptags of which 
category are written. The first (the key) is the name of the category. 
Previously there were minor and major toptags. I decided to directly use 
"genre" and "grouping". The second (the value) is the name of the metatag.

So to assign the toptags of category "genre" to the "grouping" metatag simply
change the second value.

As you can see the metatags in the "album" are actually not valid for most media
formats. They are meant to be used in naming scripts (for example a "genre"
path), because they are guaranteed to be the same for all tracks of the entire
album.


### Track metadata processor

The "track" run works very similar to the Last.fm.Plus plugin. It collects 
toptags for

- the artist ("artist" list) and
- the track ("track" list)

for each track of the album separately one by one.

Again the weight parameters are the multiplicators applied to the toptag lists.
To disable tagging using the track information and only use the artist, simply 
set the weight of "track" to 0.

If you used the Last.fm.Plus plugin the metatag names in the "tags" section will
be familiar. Each metatag is set per track. Similar to before, the first column
are the "categories" in which toptags are grouped using the search lists and the
second column are the names of the metatags in your files.


### Differences to Last.fm.Plus

When using translations, the score of both toptags are summarized, rather 
"the greater wins, the lesser is dropped".

Years and decades use a regular expression to find valid values. With decades,
both "00s" and "2000s" are valid. This can be easily customized using the
LFM_DECADE and LFM_YEAR variables.

There is no "inter tag drop". The "minimum weight" is hardcoded to 1. So toptags
with score 0 are ignored. Usually they would not appear in any of the search
lists anyway.

The "year" metatag is disabled for now.

There may be others, so best try it out yourself and see if it does the right
thing for you.


## Disclaimer

Even though this piece of software has been in use by many people including
myself for years, things could go wrong. I hope it does not cause you any 
trouble. If it does, please open an issue and maybe we can fix it.

However, since this is still a hobby/side project I cannot guarantee any 
functionality or responsiveness on requests. Also since it is free software,
maybe you can have a look at the code your self and send in improvements!


Bitcoin: 1FbMXpwsLAjCkCaiLB1uhdm5mLv892UkEy


[0]: https://github.com/fdemmer/Picard-Last.fm.ng-Plugin/releases
