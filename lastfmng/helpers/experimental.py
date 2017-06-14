# -*- coding: utf-8 -*-


class SearchTree(dict):
    def __init__(self, trunk, branches):
        # TODO add lowercase-ing to all tags
        self.trunk = trunk
        dict.__init__(self, branches)

    def get_searchlist(self, result):
        try:
            toptags = result.get(self.trunk, None)
            toptag_name = toptags[0][0].lower()
            return self.get(toptag_name, None)
        except:
            return None
