#import parc_reader
#
#
#class Mention(dict):
#
#    LEGAL_TYPES = {'antecedent', 'pronoun'}
#    def __init__(
#        self,
#        mention_type,
#        sentence_id,
#        token_span,
#        tokens=None,
#        text=None,
#        **kwargs
#    ):
#        super(Mention, self).__init__(**kwargs)
#        if mention_type not in self.LEGAL_TYPES:
#            raise ValueError('Unexpected mention type: "%s".' % mention_type)
#
#        self['mention_type'] = mention_type
#        self['sentence_id'] = sentence_id
#        self['token_span'] = parc_reader.token_span.TokenSpan(token_span)
#
#        if tokens is not None:
#            self['tokens'] = parc_reader.token_list.TokenList(tokens)
#            self['text'] = self['tokens'].text()
#
#        if text is not None:
#            self['text'] = text
#
#    def merge(self, other):
#        self['text'] += ' ' + other['text']
#        self['token_span'].extend(other['token_span'])
#        self['token_span'].sort()
#
#        # Note tokens are copied by reference!
#        self['tokens'].extend(other['tokens'])
#        self['tokens'].sort()
#
#
#
