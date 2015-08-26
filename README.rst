Picard Last.fm.ng Plugin
~~~~~~~~~~~~~~~~~~~~~~~~

This plugin has been on github for over three years. I use it all the time
and a few people have contacted me, telling me about minor issues.
Therefore I am assuming people use it and it works.

However, this is free software and if something goes wrong it is totally our
own fault!


About
=====

The original and the plus Last.fm plugins are great. I used them a lot.
However I always felt the configuration was overly complicated and the code
a bit of a mess and how the end result came to be sometimes a mystery.

Also I wanted a rocksolid way to only get exactly one genre tag at all times 
for a complete album. Plus sometimes delivered two, when just one was 
configured and there was no way to determine a single "albumgenre".

Some of the code and especially the name lists are reused from plus. Thanks
again for your work on this... RifRaf, Lukáš Lalinský, voiceinsideyou!

Differences to Last.fm.Plus
---------------------------

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


Install
=======

Copy the "lastfmng" directory to ``~/.config/MusicBrainz/Picard/plugins`` and
activate the plugin in the GUI.


Configuration
=============

The plugin does not provide a configuration dialog, but is easy to configure
by customizing the provided ``config.ini`` file.

Please use your own Last.fm API key and set it using ``lastfm_key``.
You don't need to change ``lastfm_host`` or ``lastfm_port``, but by setting
``lastfm_port`` to ``443`` https will be used.

The plugin does not just use all the tags it finds on Last.fm.
Only tags listed in the respective "search lists" will be used.

Customize the lists in the ``[searchlist]`` section of the configu file.

Translations of common tag variations are set in the ``[translations]`` section.
The first value is replaced with the second one.


Advanced configuration
======================

More advanced configuration is possible in the ``settings.py`` file.

The ``CATEGORIES`` and ``CONFIG`` dictionaries defines how the plugin finds and
selects tags for each metatag.

Contrary to the Last.fm.Plus plugin this one works via two plugin API triggers:

- register_track_metadata_processor
- register_album_metadata_processor

The Last.fm.Plus plugin only used the track metadata processor. Therefore
it could not set metatags that need to be the same for all tracks, the whole
album. The CONFIG dictionary contains the configuration for both triggers: 
"album" and "track".

Album metadata processor
------------------------

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

Track metadata processor
------------------------

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

Metatag formatting 
------------------

What is left, is the CATEGORIES dictionary. Here you can set a hard "limit" how
many of the found toptags should be used per category (and assigned to a
metatag).

If you set the limit to 1 and two toptags have exactly the same score the result
will be exactly one toptag, which one however is not clearly defined! There is
room for improvement here.

To disable writing a specific category/metatag set "enabled" to False. Setting
"sort" to True will sort the toptags alphabetically after the ones with the
highest score have been determined. Set this to False to keep the one with the
highest score in front!

Using "titlecase" you can switch fixing the case of toptags off and on. The
"separator" is used to combine more than one toptag into a metatag string and in
case not a single toptag was found for a category the value of "unknown" is set.

Searchlists and searchtrees
---------------------------

The CATEGORIES dictionary is an ordered dictionary. The sequence of categories
is important when using searchtrees. Searchtrees are an attempt to implement
Slukd's feature request for grouping-dependent genre tags
(http://forums.musicbrainz.org/viewtopic.php?pid=15871#p15871). Please see the
source comments on how to use this.


