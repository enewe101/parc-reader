import parc_reader

class Span(dict):
    """
    A span is a dictionary that has a TokenSpan under the key 'token_span',
    along with any other information on other keys.  It can adjust it's location
    in response to inserting tokens in the document.
    """

    def __init__(self, template=None, absolute=False, **kwargs):
        template = template or {}
        super(Span, self).__init__(template, **kwargs)
        self.initialize_tokens(absolute)


    def initialize_tokens(self, absolute):
        token_span = self.pop('token_span', [])
        self['token_span'] = TokenSpan(token_span, absolute=absolute)


    def add_token_ranges(self, token_ranges):
        self['token_span'].add_token_ranges(token_ranges)


    def add_token_range(self, token_range):
        self['token_span'].add_token_range(token_range)


    def accomodate_inserted_token(self, sentence_id, index):
        self['token_span'].accomodate_inserted_token(sentence_id, index)


    def relativize(self, doc):
        self['token_span'].relativize(doc)



class Constituency(Span):

    def __init__(self, *args, **kwargs):
        super(Constituency, self).__init__(*args, **kwargs)
        if 'constituent_children' not in self:
            self['constituent_children'] = []


    def accomodate_inserted_token(self, sentence_id, index):
        super(Constituency, self).accomodate_inserted_token(sentence_id, index)

        for child in self['constituent_children']:
            child.accomodate_inserted_token(sentence_id, index)


    def relativize(self, doc):
        super(Constituency, self).relativize(doc)
        for child in self['constituent_children']:
            child.relativize(doc)


def get_dfs_constituents(node):
    return parc_reader.utils.get_dfs_sequence(node, get_constituency_children)


def get_constituency_children(node):
    try:
        return node['constituent_children']
    except KeyError:
        if node['constituent_type'] != 'token':
            raise parc_reader.exceptions.ConstituentIntegrityError(
                "Constituents that have no children must be of type 'token', "
                "but this childless constituent is of type '%s'" % 
                node['constituent_type']
            )
        return []



class Attribution(dict):

    ROLES = ['source', 'cue', 'content']
    def __init__(
        self,
        template=None,
        absolute=False,
        **kwargs
    ):
        template = template or {}
        super(Attribution, self).__init__(template, **kwargs)
        self.initialize_spans(absolute)

    def initialize_spans(self, absolute):
        for span_type in self.ROLES:
            span = self.pop(span_type, [])
            self[span_type] = TokenSpan(span, absolute=absolute)

    def accomodate_inserted_token(self, sentence_id, index):
        for span_type in self.ROLES:
            self[span_type].accomodate_inserted_token(sentence_id, index)

    def relativize(self, doc):
        for span_type in self.ROLES:
            self[span_type].relativize(doc)


    def absolutize(self, doc):
        for span_type in self.ROLES:
            self[span_type].absolutize(doc)



class TokenSpan(list):
    """
    Serves as a pointer to a specific subset of tokens in a document.
    Consists of a list of tuples, having the form (start, end).
    The start and end indices follow the convention of slice notation, so the
    end'th token is not included but the start'th is.
    """

    def __init__(self, token_span=None):
        super(TokenSpan, self).__init__()

        # Collect together spans to be added.  Tolerate adding no spans, and
        # tolerate specifying single_range and / or token_span.
        token_span = [] if token_span is None else list(token_span)

        # Add all the tokens
        self.consolidated = True
        self.max = None
        self.extend(token_span)


    def relativize(self, doc):
        """
        Convert from absolute token-order addressing to sentence-relative
        addressing.
        """
        if not self.absolute:
            raise ValueError('Cannot relativize TokenSpan: already relative.')
        new_span = doc.relativize(self)
        self.absolute = False
        self.replace_with(new_span)


    def absolutize(self, doc):
        """
        Convert from sentence-relative addressing to absolute token-order
        addressing .
        """
        if self.absolute:
            raise ValueError('Cannot absolutize TokenSpan: already absolute.')
        new_span = doc.absolutize(self)
        self.absolute = True
        self.replace_with(new_span)


    def extend(self, token_ranges):
        for token_range in token_ranges:
            self.append(token_range)


    def append(self, token_range):
        try:
            start, end = token_range
        except ValueError:
            print token_range

        if start >= end or start < 0:
            raise ValueError('Invalid range: %d, %d.' % (start, end))
        if self.max >= start: 
            self.consolidated = False
        self.max = max(self.max, end)
        super(TokenSpan, self).append(token_range)


    def consolidate(self):
        if self.consolidated:
            return
        self.sort()
        new_span = []
        current_range = None
        last_end = None
        last_start = None
        for start, end in self:

            if current_range is None:
                current_range = (start, end)
                last_end = end
                last_start = start

            elif start <= last_end:
                if end > last_end:
                    current_range = (last_start, end)
                    last_end = end

            else:
                new_span.append(current_range)
                current_range = (start, end)
                last_end = end
                last_start = start

        if current_range is not None:
            new_span.append(current_range)

        # Replace elements in place
        self._replace_with_consolidated(new_span)
        self.consolidated = True


    def _replace_with_consolidated(self, token_ranges):
        """
        Directly assign token ranges, which are assumed to be already valid and
        consolidated.
        """
        self[:] = token_ranges


    def replace_with(self, token_ranges):
        """
        Assign new token ranges.  Subject ranges to validation and
        consolidation.
        """
        self[:] = []
        self.extend(token_ranges)


    def num_segments(self):
        return super(TokenSpan, self).__len__()


    def is_single_range(self):
        return self.num_segments() == 1


    def get_single_range(self):
        if not self.is_single_range():
            raise parc_reader.exceptions.NonSingleRangeError(
                'This token span has multiple ranges.')
        return self[0]


    def accomodate_inserted_token(self, idx):
        self.replace_with([
            (start+int(start>=idx), end+int(end>=idx)) 
            for start, end in self
        ])


    def envelope(self):
        self.consolidate()
        return self[0][0], self[-1][1]


    def __len__(self):
        self.consolidate()
        return sum([end - start for start, end in self])




class Coreference(dict):
    def accomodate_inserted_token(self, sentence_id, index):
        pass


