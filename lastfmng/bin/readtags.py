#!/usr/bin/python
import os
import sys
import sqlite3


try:
    count = sys.argv[1]
except IndexError:
    count = 10


try:
    conn = sqlite3.connect(os.path.expanduser('~/.config/MusicBrainz/Picard/plugins/lastfmng.db'))
    c = conn.cursor()

    c.execute("select * from toptags order by score desc limit ?", (count,))

    for row in c:
        print("{} ({})".format(row[0], row[1]))

    c.close()
except sqlite3.OperationalError:
    print("database error")
