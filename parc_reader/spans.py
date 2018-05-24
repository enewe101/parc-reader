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


    def accomodate_inserted_token(self, abs_id, sentence_id, rel_id):
        self['token_span'].accomodate_inserted_token(abs_id,sentence_id,rel_id)


    def relativize(self, doc):
        self['token_span'].relativize(doc)



class Constituency(Span):

    def __init__(self, *args, **kwargs):
        super(Constituency, self).__init__(*args, **kwargs)
        if 'constituent_children' not in self:
            self['constituent_children'] = []


    def accomodate_inserted_token(self, abs_id, sentence_id, rel_id):
        super(Constituency, self).accomodate_inserted_token(
            abs_id, sentence_id, rel_id)

        for child in self['constituent_children']:
            child.accomodate_inserted_token(abs_id, sentence_id, rel_id)


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

    def accomodate_inserted_token(self, abs_id, sentence_id, rel_id):
        for span_type in self.ROLES:
            self[span_type].accomodate_inserted_token(
                abs_id, sentence_id, rel_id)

    def relativize(self, doc):
        for span_type in self.ROLES:
            self[span_type].relativize(doc)


    def absolutize(self, doc):
        for span_type in self.ROLES:
            self[span_type].absolutize(doc)



class TokenSpan(list):
    """
    Serves as a pointer to a specific subset of tokens in a document.

    Consists of a list of tuples, having the form 

        (sentence_id, start, end)

    Absolute token_spans address tokens with respect to their ordering in the
    entire document, and have a sentence_id of `None`.  Relative token spans
    address tokens relative to a given sentence, and should have an integer for
    sentence_id 

    In either case, the start and end indices follow the convention of slice
    notation.
    """

    def __init__(
        self, token_span=None, single_range=None, absolute=False
    ):
        super(TokenSpan, self).__init__()
        self.absolute = absolute

        # Collect together spans to be added.  Tolerate adding no spans, and
        # tolerate specifying single_range and / or token_span.
        token_span = [] if token_span is None else list(token_span)
        if single_range is not None:
            token_span.append(single_range)

        # Add all the tokens
        self.consolidated = True
        self.add_token_ranges(token_span)


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


    def add_token_ranges(self, token_ranges):
        for token_range in token_ranges:
            self.add_token_range(token_range, skip_consolidation=True)
        self.consolidate()


    def _normalize_range(self, token_range):
        """Handle ommitting sentence_id when specifying a token range."""
        if len(token_range) == 3:
            return token_range
        elif len(token_range) == 2 and self.absolute:
            start, end = token_range
            return None, start, end
        else:
            raise ValueError(
                "Token ranges must take the form `(start_index, end_index)` or "
                "`(sentence_id, start_index, end_index)`.  Got %s."
                % str(token_range)
            )


    def _validate_range(self, token_range):
        sentence_id, start, end = token_range
        if self.absolute and sentence_id is not None:
            raise ValueError(
                'Absolute token ranges should have sentence_id = None.')
        if not self.absolute and sentence_id is None:
            raise ValueError(
                'Relative token ranges must have an integer sentence_id.')
        if start >= end:
            raise ValueError(
                "The start index of the token range must be less "
                "than the end index"
            )


    def add_token_range(self, token_range, skip_consolidation=False):
        token_range = self._normalize_range(token_range)
        self._validate_range(token_range)
        self._check_if_still_consolidated(token_range)
        super(TokenSpan, self).append(token_range)
        if not skip_consolidation:
            self.consolidate()


    def _check_if_still_consolidated(self, token_range):
        """
        Check if this token range comes strictly after existing token ranges,
        in which case consolidation isn't needed.
        """
        sentence_id, start, end = token_range
        if self.num_segments() > 0:
            last_range_end = self[-1][2]
            if last_range_end >= start:
                self.consolidated = False


    def consolidate(self):
        if self.consolidated:
            return
        self.sort()
        new_span = []
        current_range = None
        last_end = None
        last_start = None
        last_sentence = None
        for sentence_id, start, end in self:

            if current_range is None:
                current_range = (sentence_id, start, end)
                last_sentence = sentence_id
                last_end = end
                last_start = start

            elif sentence_id == last_sentence and start <= last_end:
                current_range = (sentence_id, last_start, end)
                last_end = end

            else:
                new_span.append(current_range)
                current_range = (sentence_id, start, end)
                last_sentence = sentence_id
                last_end = end
                last_start = start

        if current_range is not None:
            new_span.append(current_range)

        # Replace elements in place
        self._replace_with_consolidated(new_span)


    def _replace_with_consolidated(self, token_ranges):
        """
        Directly assign token ranges, which are assumed to be already valid and
        consolidated.
        """
        self[:] = token_ranges


    def replace_with(self, token_ranges, absolute=None):
        """
        Assign new token ranges.  Subject ranges to validation and
        consolidation.
        """
        self.absolute = self.absolute if absolute is None else absolute
        self[:] = []
        self.add_token_ranges(token_ranges)


    def num_segments(self):
        return super(TokenSpan, self).__len__()


    def is_single_range(self):
        return self.num_segments() == 1


    def get_single_range(self):
        if not self.is_single_range():
            raise parc_reader.exceptions.NonSingleRangeError(
                'This token span has multiple ranges.')
        return self[0]


    def accomodate_inserted_token(
        self,
        at_abs_id,
        at_sentence_id=None,
        at_rel_id=None
    ):

        insertion_point = (at_abs_id, at_sentence_id, at_rel_id)

        # Replace range elements in place
        self.replace_with([
            self.maybe_shift_range(token_range, insertion_point) 
            for token_range in self
        ])


    def maybe_shift_range(self, token_range, insertion_point):

        sentence_id, start, end = token_range
        at_abs_id, at_sentence_id, at_rel_id = insertion_point

        if sentence_id is None:
            start += int(start >= at_abs_id)
            end += int(end >= at_abs_id)
            return (None, start, end)

        else:
            start += int((sentence_id, start) >= (at_sentence_id, at_rel_id))
            end += int((sentence_id, end) >= (at_sentence_id, at_rel_id))
            return (sentence_id, start, end)


    def __len__(self):
        return sum([end-start for _, start, end in self])


    #def extend(self, iterable):
    #    super(TokenSpan, self).extend(iterable)
    #    self.sort()


    #def get_tokens(self, sentence_list):
    #    selected = []
    #    for sentence_id, start, end in self:
    #        if sentence_id is None:
    #            raise ValueError(
    #                'This token span does not have any sentence information. '
    #                'Tokens are addressed by absolute number'
    #            )
    #        choose_from_tokens = sentence_list[sentence_id].tokens()
    #        selected.extend(choose_from_tokens[start:end])
    #    return parc_reader.token_list.TokenList(selected)


