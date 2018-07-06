class Token(dict):

    def __init__(self, text, idx=None, doc=None):
        self['text'] = text
        self['annotations'] = {}
        self['id'] = idx
        self['doc'] = None
