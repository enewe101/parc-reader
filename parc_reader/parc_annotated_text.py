from parc_reader.utils import IncrementingMap as IncMap, rangify
from parc_reader.parc_sentence import ParcSentence
from bs4 import BeautifulSoup as Soup

ROLES = {'cue', 'content', 'source'}


# This reads parc files and builds a coherent representation of attribuions
# It's the PARC equivalent for the corenlp_xml_reader.  It's used by the
# ParcCorenlpReader to read parc files before merging the info contained
# therein with the info from corenlp.
class ParcAnnotatedText(object):
    '''
    Class that represents the contents of a PARC annotated article file
    using convenient python types.
    '''

    def __init__(self, parc_xml, include_nested=True):
        '''
        Provide the raw xml for a PARC annotated article file as the 
        first argument.  If include_nested is `True`, then nested 
        attributions will be read and included in the representation.  If
        false, nested attributions will be skipped.  When nested 
        attributions are skipped, then, among attributions that compete
        to include the same token(s) in their span, only one will be kept
        in the final representation: whichever one occurs textually first
        in the PARC file.
        '''

        self.include_nested = include_nested
        soup = Soup(parc_xml, 'html.parser')
        self.sentences = []
        sentence_tags = soup.find_all('sentence')

        for sentence_tag in sentence_tags:

            sentence = ParcSentence(
                {'tokens':[], 'attributions':{}}
            )
            self.sentences.append(sentence)

            word_tags = sentence_tag.find_all('word')
            current_attribution_spans = {}
            attribution_priority = IncMap()
            conflict_sets = set()
            for word_id, word_tag in enumerate(word_tags):

                token = {
                    'word': unescape(word_tag['text']),
                    'pos': word_tag['pos'],
                    'lemma': word_tag['lemma']
                }

                attributions = word_tag.find_all('attribution')
                viable_attributions = []
                for attribution in attributions:

                    # Get the info characterizing this token's role in this
                    # attribution
                    role = attribution.find('attributionrole')['rolevalue']
                    _id = attribution['id']

                    # Keep track of the viable attributions that are 
                    # competing for this word.  This is important if 
                    # include nested is false, because then we allow only 
                    # one attribution to "own" a token.  We can also
                    # pre-emptively eliminated attributions explicitly 
                    # flagged as nested
                    # NOTE: Should be qualified by ``if not include_nested``...
                    if 'Nested' in _id:
                        continue
                    viable_attributions.append(_id)

                    # Keep track of the order in which attributions were
                    # initially encountered
                    attribution_priority.add(_id)

                    if _id not in current_attribution_spans:
                        current_attribution_spans[_id] = {
                            'id': _id,
                            'cue':[], 'content':[], 'source':[]
                        }

                    # Add this word (referenced by its id) to this role
                    # of this attribution
                    current_attribution_spans[_id][role].append(word_id)

                # If more than one viable attribution is assigned to this 
                # word, note the potential conflict.  If nested attributions
                # are not allowed, then these are indeed conflicts and will
                # need to be resolved
                if len(viable_attributions) > 1:
                    conflict_sets.add(tuple(viable_attributions))

                sentence['tokens'].append(token)

            # If we don't want to include nested attributions, then we
            # will now resolve conflicts where words have been found 
            # belonging to multiple attributions
            if not self.include_nested:
                for conflict_set in conflict_sets:
                    # Filter ids in the conflict set that are still viable
                    viable_ids = [
                        _id for _id in conflict_set 
                        if _id in current_attribution_spans
                    ]

                    # Sort viable attribution_ids into the order in which
                    # they were first encountered
                    viable_ids.sort(
                        key=lambda _id: attribution_priority[_id]
                    )

                    # Delete all but the highest priority attribution
                    for _id in viable_ids[1:]:
                        del current_attribution_spans[_id]


            # TODO: put attributions onto the tokens
            for _id in current_attribution_spans:
                for role in ROLES:
                    for token_id in current_attribution_spans[_id][role]:
                        sentence['tokens'][token_id]['role'] = role
                        sentence['tokens'][token_id]['attribution_id'] = (
                            _id)
                        sentence['tokens'][token_id]['attribution'] = (
                            current_attribution_spans[_id]
                        )


            # Currently the spans in attributions are just lists of 
            # token ids.  Group together contigous ids using a 
            # (start, stop) notation compatible with the range() function
            for _id in current_attribution_spans:
                for role in ROLES:
                    current_attribution_spans[_id][role] = rangify(
                        current_attribution_spans[_id][role]
                    )

            # Add the rangified attribution spans
            sentence['attributions'] = current_attribution_spans.values()



def unescape(token):
    '''
    Reverses token escaping that has been done in PARC3
    '''

    # Restore round and square brackets
    if token == '-LRB-':
        return '('
    if token == '-RRB-':
        return ')'
    if token == '-RCB-':
        return ']'
    if token == '-LCB-':
        return '['

    # Finally, remove any backslashes, which are used to escape what
    # parc considers to be special characters, but which should be 
    # printed literally
    return token.replace('\\', '')

