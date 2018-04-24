import parc_reader


class TokenSpan(list):
    """
    A list of 2-tuples, with each 2-tuple specifying the start and end indices
    of a span of tokens.  Helps to address specific token subsets.
    """

    def __init__(self, tokenspan=None, single_range=None, start=None, end=None):
        super(TokenSpan, self).__init__()
        if start is not None and end is not None:
            self.append((start, end))
        elif single_range is not None:
            self.append(single_range)
        elif tokenspan is not None:
            self.extend(tokenspan)


    def is_single_range(self):
        return len(self) == 1


    def get_single_range(self):
        if not self.is_single_range():
            raise NonSingleRangeError('This token span has multiple ranges.')
        return self[0]


    def select_tokens(self, tokens):
        selected = []
        for start, end in self:
            selected.extend(tokens[start:end])
        return parc_reader.token_list.TokenList(selected)


class NonSingleRangeError(Exception):
    pass

