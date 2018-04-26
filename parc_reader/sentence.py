#import parc_reader
#
#class Sentence(dict):
#    """
#    Bind the Sentence to a specific document.  The sentence references a set of
#    tokens in the document based on their index.
#    """
#
#    def __init__(self, template=None, **kwargs):
#
#        if template is None: 
#            template = {}
#
#        super(Sentence, self).__init__(template, **kwargs)
#
#        self.initialize_tokens()
#
#
#    def initialize_tokens(self):
#        token_span = self.pop('token_span', [])
#        self['token_span'] = parc_reader.token_span.TokenSpan(token_span)
#
#
#    def accomodate_inserted_token(self, abs_id, sentence_id=None, rel_id=None):
#        self['token_span'].accomodate_inserted_tokens(abs_id, None, None)
#
#
#
#
