class TokenList(list):

    def __init__(self, tokens=None):
        if tokens is not None:
            self.extend(tokens)

    def sort(self):
        super(TokenList, self).sort(key=lambda t: (t['sentence_id'], t['id']))

    def text(self):
        return ' '.join([t['text'] for t in self])

