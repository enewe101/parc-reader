'''
This module contains a couple utility classes used by the ParcCorenlpReader,
and ParcAnnotatedText.
'''


def rangify(iterable):
    '''
    Converts a list of indices into a list of ranges (compatible with the
    range function).  E.g. [1,2,3,7,8,9] becomes [(1,4),(7,10)].
    The iterable provided must be sorted. Duplicate indices are ignored.  
    '''
    ranges = []
    last_idx = None
    for idx in iterable:

        if last_idx is None:
            start = idx

        elif idx - last_idx > 1:
            ranges.append((start, last_idx + 1))
            start = idx

        last_idx = idx

    if last_idx is not None:
        type(ranges)
        ranges.append((start, last_idx + 1))

    return ranges



class IncrementingMap(dict):
    '''
    Assigns incrementing integer keys to arbitrary hashable objects, 
    starting from 0.

    After calling `incrementing_map.add(hashable)`, the key for the object 
    can be retrieved using `incrementing_map[hashable]`, or, the object
    can be looked up using its id by doing `incrementing_map.key(key)`.

    Objects that have the same hash are considered identical, and get the
    same key.  Calling `incrementing_map.key(key)` with their key would
    return the first such object added.
    '''

    def add(self, key):
        if key not in self:
            self[key] = self.get_incrementing_id()
            self._get_keys().append(key)


    def get_incrementing_id(self):
        try:
            self._current_id += 1
        except AttributeError:
            self._current_id = 0
        return self._current_id


    def _get_keys(self):
        '''
        This getter is private, and covers the case where self._keys is
        not yet defined.  The first time it is called, self._keys is
        initialized to be an empty list.
        '''
        try:
            return self._keys
        except AttributeError:
            self._keys = []
            return self._keys


    def key(self, idx):
        return self._get_keys()[idx]


    def keys(self):
        return [k for k in self._get_keys()]


def get_span(sentence, start, stop):
    return sentence['tokens'][start:stop]



def get_spans(sentence, spans, elipsis=True):
    '''
    This function retrieves the tokens for a given list of 
    spans.  A span is a contiguous range of tokens, and a list of
    spans contains one or more contiguous range of tokens.  

    When retrieving tokens for a list of spans that contains ore than
    one span, we visually indicate the discontinuity that exists 
    between spans, by adding a false token that looks like an elepsis
    '''
    tokens = []
    first = True
    for span in spans:

        # We add an elipses false token to visually show that 
        # a discontinuity exists between two spans.
        if first:
            first = False
        elif elipsis:
            tokens.append(
                {'word':'...'}
            )

        # Collect the tokens represented by the span
        try:
            tokens.extend(get_span(sentence, *span))
        except TypeError:
            print span
            raise

    return tokens


# CONSTITUENCY-RELATED FUNCTIONS
def get_dfs_sequence(node, get_children, sequence=None, depth=0):
    if sequence is None:
        sequence = []
    sequence.append((depth, node))
    for child in get_children(node):
        get_dfs_sequence(child, get_children, sequence, depth+1)
    return sequence


def non_text_children(parent):
    for child in parent.contents:
        if child.name:
            yield child


def first_non_text_child(parent):
    for child in parent.contents:
        if child.name:
            return child

