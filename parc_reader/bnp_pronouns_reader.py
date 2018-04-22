import parc_reader
import os
import re
import t4k
import copy

BNP_PRONOUNS_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.pron')
BNP_SENTENCES_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.sent')


def read_sentences(path=BNP_SENTENCES_PATH):
    documents = {}
    state = 'root'
    for i, line in enumerate(open(BNP_SENTENCES_PATH)):

        line = line.rstrip()
        #print '%d\t%s' % (i, repr(line))

        if state == 'root':

            if line[0] == '(':
                article_num = parse_article_num(line)
                state = 'in_article'
                document = {'sentences':[], 'tokens':TokenList()}
                documents[article_num] = document

            else:
                raise ValueError(
                    'Expecting document start or end of file, but got "%s"' 
                    % line
                )

        elif state == 'in_article':

            if line == ')':
                state = 'root'

            elif line.startswith('\tS'):
                sentence_spec, content = line.lstrip().split(':', 1)
                sentence_id = parse_sentence_id(sentence_spec)
                if sentence_id != len(document['sentences']):
                    raise ValueError(
                        'Expecting sentence %d but got %d' 
                        % (len(document['sentences']), sentence_id)
                    )

                tokens = TokenList([
                    {'text': t, 'id': i, 'sentence_id': sentence_id}
                    for i, t in enumerate(content.lstrip().split())
                ])

                start_index = len(document['tokens'])
                document['tokens'].extend(tokens)
                end_index = len(document['tokens'])

                document['sentences'].append({
                    'id': sentence_id,
                    'start_index': start_index,
                    'end_index': end_index,
                    'tokens': tokens
                })

            elif line == ')':
                stte = 'root'

            else:
                raise ValueError(
                    'Expecting sentence or document end  but got "%s".' % line)

        else:
            raise ValueError('Unexpected state: "%s".' % state)

    return documents


def to_char_sequence(bnp_doc):
    chars = []
    for token in bnp_doc['tokens']:
        for char in token['text']:
            chars.append({'char':char, 'token':token})
    return chars
 


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
        return TokenList(selected)




WHITESPACE = re.compile('\s+')
class AnnotatedDocument(object):

    def __init__(self,
        doc,
        coreferences=None,
        doc_num=None
    ):
        self.doc_num = doc_num
        self.initialize_document(doc)
        self.initialize_coreferences(coreferences)


    def initialize_document(self, doc):
        self.tokens = copy.deepcopy(doc['tokens'])
        self.sentences = copy.deepcopy(doc['sentences'])


    def initialize_coreferences(self, coreferences=None):
        self.next_coreferences_id = 0
        self.coreferences = {}
        self.add_coreferences(coreferences)


    def get_reference_id(self):
        self.next_coreferences_id += 1
        return self.next_coreferences_id - 1


    def validate_text_match(self, mention, mention_tokens):
        # Check that tokens we found contain the text we expected
        # (ignoring differences in whitespace).
        found_mention_text = ''.join(t['text'] for t in mention_tokens)
        found_text_no_white = WHITESPACE.sub('', found_mention_text)
        expected_text_no_white = WHITESPACE.sub('', mention['text'])
        if found_text_no_white != expected_text_no_white:
            raise ValueError(
                'While adding a mention within a coreference chains, '
                'the tokens found for the mention did not match the '
                'Expected text.  '
                'expected "%s", but found "%s"'
                % (expected_text_no_white, found_text_no_white)
            )


    def raise_non_matching(self, expected_text, found_text):

        raise ValueError(
            'While adding a mention within a coreference chains, '
            'the tokens found for the mention did not match the '
            'Expected text.  '
            'expected "%s", but found "%s"'
            % (expected_text, found_text)
        )


    def check_tokens_match(self, mention, mention_tokens):
        found_token_text = ''.join(t['text'] for t in mention_tokens)
        if not text_match_nowhite(found_token_text, mention['text']):
            self.raise_non_matching(found_token_text, mention['text'])


    def get_mention_tokens(self, mention):
        sentence = self.sentences[mention['sentence_id']]
        #start, end = mention['start'], mention['end']
        #return sentence['tokens'][start:end]
        return mention['token_span'].select_tokens(sentence['tokens'])


    def accumulate_representative(representative, mention):
        """
        merges together multiple mentions
        """
        if representative is None:
            return copy.copy(mention)
        representative['tokens'].extend(mention['tokens'])
        representative['token_span'].extend(mention['token_span'])
        return representative


    def add_coreferences(self, coreferences=None):

        if coreferences is None:
            return

        for reference in coreferences:

            # Make an internal copy and keep the passed-in object untouched.
            reference_id = self.get_reference_id()
            new_reference = {
                'id': reference_id,
                'mentions': [],
            }
            self.coreferences[reference_id] = new_reference

            representative = None
            for mention in reference:

                mention_tokens = self.get_mention_tokens(mention)
                self.check_tokens_match(mention, mention_tokens)
                
                new_mention = {
                    'token_span': TokenSpan(mention['token_span']),
                    'sentence_id': mention['sentence_id'],
                    'tokens': mention_tokens,
                    'mention_type': mention['mention_type'],
                    'reference': new_reference
                }
                new_reference['mentions'].append(new_mention)

                representative = self.accumulate_representative(
                    representative, new_mention)
                print_stuff(mention,sentence,start, end,mention_tokens)

            if representative is not None:
                new_reference['representative'] = representative

            if reference_id > 4:
                break
                

def remove_whitespace(string):
    return WHITESPACE.sub('', string)


def text_match_nowhite(text1, text2):
    text1_nowhite = remove_whitespace(text1)
    text2_nowhite = remove_whitespace(text2)
    return text1_nowhite == text2_nowhite


def print_stuff(mention,sentence,start, end,mention_tokens):
    print mention
    print
    print 'mention', mention
    print 'sentence', sentence
    print '(start, end)', (start, end)
    print 'mention_tokens', mention_tokens


def read_bnp_pronoun_dataset(
    pronouns_path=BNP_PRONOUNS_PATH,
    sentences_path=BNP_SENTENCES_PATH
):

    dataset = []
    documents = read_sentences()
    pronoun_annotations = read_pronouns()

    seen_docs = set()
    for doc_num, coreferences in pronoun_annotations.items():

        print '\n\t--- %d ---' % doc_num
        doc = documents[doc_num]
        annotated_doc = AnnotatedDocument(doc, coreferences, doc_num=doc_num)
        seen_docs.add(doc_num)
        dataset.append(annotated_doc)

        #
        # LEFT OFF
        #
        # iterate through coreference chains of the pronoun doc
        # and use their indices to attach pronoun information to 
        # the sent_doc's tokens.
        #

        if doc_num == 4:
            break

    unseen_articles = set(pronoun_annotations.keys()) - seen_docs
    if len(unseen_articles) > 0:
        raise ValueError(
            'Some articles were not seen: %s.' 
            #% ', '.join(t4k.strings(unseen_articles))
        )

    return dataset




def read_pronouns(path=BNP_PRONOUNS_PATH):

    state = 'root'
    documents = {}

    #print path

    for i, line in enumerate(open(path)):

        line = line.rstrip()

        #print '%d\t%s' % (i,line)

        if state == 'root':
            if line[0] == '(':
                article_num = parse_article_num(line)
                state = 'in_article'
                coreferences = []
                documents[article_num] = coreferences

            else:
                raise ValueError(
                    'Expected document start openning bracket.  '
                    'Got "%s" on line %d.' % (line, i)
                )

        elif state == 'in_article':

            if line[0] == ')':
                coreferences = None
                state = 'root'

            elif line == '    (':
                state = 'in_reference'
                reference = []
                coreferences.append(reference)

            else:
                raise ValueError(
                    'Expected coreference chain start or document end.  '
                    'Got "%s" on line %d.' % (line, i)
                )

        elif state == 'in_reference':

            if line.startswith('\tAntecedent'):
                reference.append(parse_mention(line))

            elif line.startswith('\tPronoun'):
                reference.append(parse_mention(line))

            elif line == '    )':
                state = 'in_article'
                reference = None

            else:
                raise ValueError(
                    'Expected antecedent or pronoun definition or end of '
                    'coreference chain.  Got "%s" on line %d.' % (line, i)
                )

    if state != 'root':
        raise ValueError(
            'Unexpected end of file.  Expected to be at root state, '
            'but currently in "%s" state; on line %d.' % (state, i)
        )

    return documents


def as_character_sequence():
    pass



ARTICLE_NUM_MATCHER = re.compile('\(WSJ(\d\d\d\d)')
def parse_article_num(line):
    try:
        return int(ARTICLE_NUM_MATCHER.match(line).groups()[0])
    except: 
        raise ValueError('Could not parse article number.  Got "%s".' % line)


def parse_mention(line, expected_mention_type=None):

    mention_type, location_spec, text = t4k.stripped(line.split('->'))
    sentence_spec, token_range_spec = location_spec.split(':')
    sentence_id = parse_sentence_id(sentence_spec)
    token_span = TokenSpan(single_range=parse_token_range(token_range_spec))

    if expected_mention_type is not None:
        if mention_type != expected_mention_type:
            raise ValueError(
                ('Expected definition for mention type "%s".  '
                'Got "%s" instead.') % (expected_mention_type, line)
            )

    return Mention(**{
        'mention_type': mention_type.lower(),
        'sentence_id': sentence_id,
        'token_span': token_span,
        'text': text
    })


class Mention(dict):

    LEGAL_TYPES = {'antecedent', 'pronoun'}
    def __init__(self, mention_type, sentence_id, token_span, text):
        if mention_type not in self.LEGAL_TYPES:
            raise ValueError('Unexpected mention type: "%s".' % mention_type)
        self['mention_type'] = mention_type
        self['sentence_id'] = sentence_id
        self['token_span'] = TokenSpan(token_span)
        self['text'] = text

    def merge(self, other):
        self['text'] += ' ' + other['text']
        self['token_span'].extend(other['token_span'])
        self['token_span'].sort()

        # Note tokens are copied by reference!
        self['tokens'].extend(other['tokens'])
        self['tokens'].sort()



class TokenList(list):

    def __init__(self, tokens=None):
        if tokens is None:
            self.tokens = []
        else:
            self.tokens = list(tokens)


    def sort(self):
        super(TokenList, self).sort(
            key=lambda t: (t['sentence_id'], t['id'])
        )
        


SENTENCE_ID_MATCHER = re.compile('S(\d+)')
def parse_sentence_id(sentence_spec):
    """
    Parses sentence designations, which look like, e.g.:
    S12 (=> 12th sentence).  The input uses 1-based indexing, and we'll 
    convert to 0-based indexing to make referencing and slicing simpler.
    """
    one_based_index = int(SENTENCE_ID_MATCHER.match(sentence_spec).groups()[0])
    zero_based_index = one_based_index - 1
    return zero_based_index


def parse_token_range(token_range_spec):
    """
    Parses the character range provided by specification of antecedent and 
    pronoun instances.  We need to fix two indexing problems:
        (1) The input uses 1-based indexing, but we want 0-based;
        (2) In the character range provided by the input, which consists of
            start and end indices, the end index corresponds to the index of
            the last token, wheras for consistency with python slice notation,
            we want the end index to correspond to the next-after-last token.

    Both of these problems can be fixed by subtracting 1 from the start index.
    """
    offset1_str, offset2_str = token_range_spec.split('-')
    offset1 = int(offset1_str) - 1
    offset2 = int(offset2_str)
    return offset1, offset2



