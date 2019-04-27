# Picard Last.fm.ng Plugin

## About

Picard Last.fm.ng is not exactly a rewrite of the other popular last.fm
plugins for MusicBrainz Picard. It was developed as an alternative and with
slightly different design goals.

Initial motivation was more flexible configuration and more predictable
outcomes. It also used the Last.fm API v2.0 from the start.

It might work for you as a drop-in replacement and a lot is possible with
simple configuration changes, but there are as many naming and tagging
schemes as there are music lovers.

Thanks go out to contributors of the original and plus last.fm plugins!
They were invaluable as a starting point.


### Features

 - Last.fm API v2.0 support
 - uses both Picard API calls for per-album and per-track last.fm-tags
 - special "albumgrouping" and "albumgenre" variables for consistent
   per-album tagging and naming
 - comprehensive, ini-file based configuration
 - save tags as multiple tags or combined to a string
 - ignore featured artists when looking up last.fm-tags

Please see the "How it works" section for a better understanding on what
the plugin does.


### FAQ

It's ok to ask questions using github issues, but please check if your
question was already answered before. They are usually labeled with "faq":

https://github.com/fdemmer/Picard-Last.fm.ng-Plugin/issues?utf8=%E2%9C%93&q=is%3Aissue+label%3Afaq+


## Install

Download the latest release from the github [releases][0] page.

Extract the "lastfmng" directory in the archive to your local user's plugin
directory:

 - Windows: ``%APPDATA%\MusicBrainz\Picard\plugins``
 - Linux/MacOS: ``~/.config/MusicBrainz/Picard/plugins``

(Do not just put all the files contained inside the "lastfmng" directory
there, put the whole directory there!
eg. ``~/.config/MusicBrainz/Picard/plugins/lastfmng/...``)

Start or restart Picard to load the plugin and enable it in the options
dialog for plugins.


### Updating

It is recommended to backup your ``config.ini`` and delete the existing
"lastfmng" directory before extracting a new version to the plugins directory.

Then copy the configuration file back in place.

Sorry for the inconvenience.


## Configuration

The plugin does not provide a configuration dialog, but is easy to configure
using ini-files.

The provided ``defaults.ini`` contains all available settings.

To customize settings create a new empty file called ``config.ini`` with only
the settings you want to change. There is no need to copy the defaults!
If a ``config.ini`` file is found, it will be loaded after ``defaults.ini``
overwriting the default settings with yours.

**Make sure you save the files in UTF-8 encoding!**


### Naming rules

This plugin is supposed to be used with the following naming rules:

    $rreplace(%subdirectory%/$if2(%albumgrouping%,Unknown)/$if2(%albumartist%,%artist%) - $if($if2(%originalyear%,%originaldate%,%date%),$left($if2(%originalyear%,%originaldate%,%date%),4),0000) - $replace(%album%,...,…)/$replace(%album%,...,…) - $if($ne(1,%totaldiscs%),%discnumber%,)$num(%tracknumber%,2) - %artist% - %title%,[*|:"<>?],~)

It builds a basic directory structure using the ``%subdirectory%`` and
``%albumgrouping%`` variables. The ``%albumgrouping%`` is configured to only
one last.fm-tag by default and guaranteed to be consistent per album.

Set this script, to generate the ``%subdirectory%``:

```
$set(subdirectory,Archive Albums)
$if($in(%releasetype%,soundtrack),
    $set(subdirectory,Archive Soundtracks)
    $set(genre,Soundtrack)
)
$if($in(%releasetype%,compilation),
    $if($eq(%albumartist%,Various Artists),
        $set(subdirectory,Archive Compilations))
)
```

It puts all albums, that look like soundtracks or compilations in a different
top-level directory, than "normal" albums. Also it adds a tag called
"Soundtrack" to the "genre" metatag of all tracks that are soundtracks.


### Last.fm API

The plugin should work out of the box with the shipped API key.

However, please use your own Last.fm API key and set it using ``lastfm_key``.
You don't need to change ``lastfm_host`` or ``lastfm_port``, but by setting
``lastfm_port`` to ``443`` https will be used.

If you want you can put the Last.fm related settings in an extra file called
``lastfm.ini``.


## How it works

The basic concept is this:

1. Download _last.fm-tags_ for the album, the artist of the album (if there
   is one) or each artist of each track and each track.
   A "last.fm-tag" is just words users have assigned; it can be anything like
   "my favourite", "heard last night", "sucks" or terms we are more interested
   in like "classic", "80s" or "death metal".
2. This step filters and separate all the last.fm-tags into categories
   (like "grouping", genre", "mood", "country", ...)
3. Then sort the last.fm-tag by popularity in each category.
   Last.fm provides a numeric popularity _score_ for each tag.
4. Assign the the most popular last.fm-tag in each category to a variable,
   that can be used in a script, naming rule or by Picard directly to
   assign to a a metatag of a file (eg. the "genre" id3 tag).


### Step 1

Last.fm provides "tags" for artists, albums and tracks.

This plugin is triggered via two Picard plugin API calls:

- ``register_track_metadata_processor``
- ``register_album_metadata_processor``

So the collection of last.fm-tags also happens in two steps: once for the
album and for each track.

- In the per-track call for each track the last.fm-tags for the track's
  artist and the track itself is fetched from last.fm.

- In the per-album call the last.fm-tags for album title is fetched.
  To cover both compilations and single artist albums, all artists appearing
  on any track of the the album are looked up. In addition also all
  last.fm-tags of the tracks are considered again.
  In other words: the tags of each track count towards the tagging of the
  album.

Data fetched from last.fm is cached to avoid redundant API requests.


### Step 2

The plugin uses a fixed list of categories, think of them as _buckets_ where
last.fm-tags are put into by "topic":

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

Translations of common tag variations are set in the ``[translations]``
section. The first value is replaced with the second one.

**Make sure you add your translation to the searchlist or it will not be used!**


#### Category configuration

For each category there is a section in the config file.

To disable using a specific category set ``enabled`` to False. You will not
get any data for that category/metatag then.

If you set the ``limit`` to 1 and two "tags" have exactly the same popularity
the result will be exactly one, which one however is not clearly defined!
There is room for improvement here.

Setting ``sort`` to True will sort the "tags" alphabetically *after* the ones
with the highest popularity have been determined. Set this to False to keep
the one with the highest popularity in front (from left to right)!

Using ``titlecase`` you can switch fixing the case of last.fm-tags off and on.
The ``separator`` is used to combine more than one toptag into a metatag
string and in case not a single toptag was found for a category the value of
``default_unknown`` is set.


### Step 3

Popularity of a last.fm-tag is based on the score received from last.fm.
A higher score indicates a more popular tag. We do not get absolute numbers.

Also, since last.fm tagging is crowd-sourced the quality varies greatly.
It is also possible that different artists share the same name, so you might
get tags that were actually meant for someone else under that name.

People could have also completely different opinions about genres and simply
tag music "wrong".

Nevertheless the plugin works with what it gets.

#### last.fm-tag score processing

Weight parameters are the multipliers applied to the last.fm-tag's score.

- For per-track tagging the plugin puts an emphasis on variation and detail.
  The assumption is, that the last.fm-tags put by users on the track are
  describing the song better, than the tags put on the artist of the track.

  - last.fm-tags of the track itself 80%
  - last.fm-tags of a track's artist are weighed by only 20%

- For per-album tagging the plugin aims for consistency over the artist's
  body of work.

  - last.fm-tags from all artists on the album are 55%
  - last.fm-tags from all tracks on the album are 30%
  - last.fm-tags of the album itself are weighed only 15%

  Main reason for the low album weight is to get consistency, to be able to
  use the per-album tagging comfortably in a directory/naming schema -- to
  keep all albums of an artists grouped together.

  Another anecdotal reasoning for low weight of the album:

    New releases are often tagged very little and more "wrong", than later when
    more people have tagged the album and the opinions are "evened out". By
    reducing the weight of the album tag scores, that "wrongfulness" is reduced
    and covered up by the usually more estabilished, reliable artist tags.

  Note about "all artists on the album":

    When an album features 10 tracks, of which 9 are from the same artist and
    there is a single guest on the record, the guest artist's score does of
    course _not_ count the same as the guy singing on 9 tracks!

    In this example the artist tags are already multiplied by 9 for the one
    guy and ony 1 for the other before going into the weighing process.

    For example:
    Just because "Disorder" on Slayer's "Soundtrack of the Apocalypse" is
    featuring Ice-T, you won't get any "hip-hop" in the albumgenre.

    If you know a better example for an "album with unusual guest star" let
    me know ;)

The weight parameters are not exposed in the configuration files.
If you _really_ want to play with those, see settings.py.


### Step 4

Finally the sorted and weighed last.fm-tags are ranked by resulting score in
their category-buckets and limited to only the top results(s)
(see ``limit`` parameter in ``config.ini``).

The result of each category is then put into a variable Picard can use.
(see ``metatag-album`` and ``metatag-track`` in ``config.ini``)

You can change the variable names in the configuration file, but keep in mind,
that Picard maps certain variable names to metatags it writes to files:

  https://picard.musicbrainz.org/docs/tags/

The ``metatag_album`` parameter in ``config.ini`` is only available for the
categories grouping, genre and mood and is used for the result of the
per-album tagging.


### Differences to Last.fm.Plus

When using translations, the score of both last.fm-tags are summarized, rather
"the greater wins, the lesser is dropped".

Years and decades use a regular expression to find valid values. With decades,
both "00s" and "2000s" are valid. This can be easily customized using the
LFM_DECADE and LFM_YEAR variables.

There is no "inter tag drop". The "minimum weight" is hardcoded to 1. So last.fm-tags
with score 0 are ignored. Usually they would not appear in any of the search
lists anyway.

The "year" metatag is disabled for now.

Last.fm.Plus only uses the per-track trigger.


## Disclaimer

Even though this code has been in use by many people for years things can go
wrong. If they do, please open an issue and maybe we can fix it.

Motivational bitcoin welcome: bc1qe0hs8h7wv200la0tdymlj3rgh0yqe040p2v4c6


[0]: https://github.com/fdemmer/Picard-Last.fm.ng-Plugin/releases
