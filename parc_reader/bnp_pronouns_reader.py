import parc_reader
import os
import re
import t4k
import copy
import bs4

BNP_PRONOUNS_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.pron')
BNP_SENTENCES_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.sent')
BBN_ENTITY_TYPES_DIR = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'WSJtypes-subtypes')



def read_bbn_entity_types(entity_types_path=BBN_ENTITY_TYPES_DIR):
    print "Reading BBN entity types.  This will take a minute..."
    annotated_docs = {}
    for path in t4k.ls(entity_types_path):
        annotated_docs.update(parse_bbn_entity_types_file(open(path).read()))
    return annotated_docs



def parse_bbn_entity_types_file(xml_string):
    xml_doc = bs4.BeautifulSoup(xml_string, 'lxml')
    annotated_docs = {}
    for doc in xml_doc.find_all('doc'):
        doc_num = parse_doc_num(doc.find('docno').text.strip())
        tokens = []
        annotated_doc = {'tokens':tokens}
        annotated_docs[doc_num] = annotated_doc
        for child in doc.contents:
            if child.name == 'docno':
                continue
            if is_text_node(child):
                tokens.extend(get_text_tokens(child))
            else:
                tokens.extend(get_annotated_tokens(child))
    return annotated_docs


def get_annotated_tokens(element):
    annotation = get_annotation(element)
    return [
        dict(bbn_entity=annotation, text=text) 
        for text in element.text.strip().split()
    ]


def get_annotation(element):
    return tuple([element.name] + element['type'].split(':'))



def get_text_tokens(text_element):
    return [{'text':text} for text in text_element.strip().split()]


def is_text_node(element):
    """
    You can tell that an element is a text node if it has no tag *name*.
    """
    return element.name is None


def read_bnp_pronoun_dataset(
    pronouns_path=BNP_PRONOUNS_PATH,
    sentences_path=BNP_SENTENCES_PATH
):

    dataset = []
    documents = read_sentences()
    pronoun_annotations = read_pronouns()
    entity_types = read_bbn_entity_types()
    print 'Combining annotations from multiple sources...'

    seen_docs = set()
    for doc_num, coreferences in pronoun_annotations.items():
        try:
            doc = documents[doc_num]
            entity_type_annotations = entity_types[doc_num]
        except KeyError:
            print "skipping doc# %d due to missing annotations" % doc_num
            continue
        dataset.append(AnnotatedDocument(
            doc,
            doc_num=doc_num,
            coreferences=coreferences,
            entity_types=entity_type_annotations
        ))
        seen_docs.add(doc_num)

    unseen_articles = set(pronoun_annotations.keys()) - seen_docs
    if len(unseen_articles) > 0:
        print (
            "Warning: some articles were not included: %s." 
            % ', '.join(sorted(t4k.strings(unseen_articles)))
        )

    return dataset



WHITESPACE = re.compile('\s+')
class AnnotatedDocument(object):

    def __init__(self,
        doc,
        doc_num=None,
        coreferences=None,
        entity_types=None
    ):
        # Left off: about to incorporate entity type annotatios.
        self.doc_num = doc_num
        self.initialize_document(doc)
        self.initialize_coreferences(coreferences)
        self.initialize_entity_types(entity_types)
        self.validate_mention_tokens()


    def initialize_entity_types(self, entity_types):

        token_pointer = 0
        for other_token in entity_types['tokens']:


            self_token = self.tokens[token_pointer]
            self_text, other_text = self_token['text'], other_token['text']

            #print self_text, other_text

            # Skip the stray apostraphe in doc 63.
            if self.doc_num == 63:
                if self_token['abs_id'] == 291:
                    continue

            # If they are the same token, merge the annotations
            if self_text == other_text:
                self_token.update(other_token)

            # If the new token is a subset of the existing token, split
            # the existing token
            elif self_text.startswith(other_text):
                #print (
                #    '\t\tdoc #%d, token %d, splitting "%s" into "%s" and "%s"'
                #    % (
                #        self.doc_num, self_token['abs_id'], self_text,
                #        other_text, self_text.split(other_text, 1)[1]
                #    )
                #)
                self_token, remainder = self.split_token(self_token, other_text)
                self_token.update(other_token)

            else:
                raise ValueError(
                    '\t\tdoc #%d, token %d, expecting "%s" got "%s"'
                    % (self.doc_num,self_token['abs_id'],self_text,other_text)
                )

            token_pointer += 1


    def split_token(self, token, partial_text):

        sentence_id = token['sentence_id']
        abs_index = token['abs_id'] + 1
        rel_index = token['id'] + 1

        remainder = token['text'].split(partial_text, 1)[1]
        token['text'] = partial_text
        remainder_token = dict(token, text=remainder)

        self.insert_token(abs_index, sentence_id, rel_index, remainder_token)

        return token, remainder_token


    def insert_token(self, abs_index, sentence_id, rel_index, token):
        self.tokens.insert(abs_index, token)
        self.sentences[sentence_id]['tokens'].insert(rel_index, token)

        # Do a bunch of index fixing to account for the newly inserted token
        self.write_token_ids()
        self.fix_sentence_indices(abs_index)
        self.fix_mentions_tokens(abs_index, sentence_id)


    def validate_mention_tokens(self):

        for reference_id, reference in self.coreferences.items():
            if 'representative' in reference:
                rep = reference['representative']
                expected_text = rep['text']
                found_text = self.get_mention_tokens(rep).text()

                if not text_match_nowhite(expected_text, found_text):
                    raise ValueError(
                        'Non-matching text in doc# %d, reference# %d, '
                        'mention# [rep]. Expected "%s", found "%s".'
                        % (self.doc_num,reference_id,expected_text,found_text)
                    )

            for mention_id, mention in enumerate(reference['mentions']):
                expected_text = mention['text']
                found_text = self.get_mention_tokens(mention).text()

                if not text_match_nowhite(expected_text, found_text):
                    raise ValueError(
                        'Non-matching text in doc# %d, reference# %d, '
                        'mention# %d. Expected "%s", found "%s".'
                        % (
                            self.doc_num,reference_id,mention_id,
                            expected_text,found_text
                        )
                    )


    def fix_sentence_indices(self, abs_index):
        for sentence in self.sentences:
            sentence['token_span'] = self.fix_token_span(
                abs_index, sentence['token_span'])


    def fix_mentions_tokens(self, abs_index, sentence_id):
        for reference in self.coreferences.values():
            if 'representative' in reference:
                self.fix_mention_tokens(
                    abs_index, sentence_id, reference['representative'])
            for mention in reference['mentions']:
                self.fix_mention_tokens(abs_index, sentence_id, mention)


    def fix_token_span(self, abs_index, token_span):
        return parc_reader.token_span.TokenSpan([
            (maybe_increment(start,abs_index), maybe_increment(stop,abs_index))
            for start, stop in token_span
        ])


    def fix_mention_tokens(self, abs_index, sentence_id, mention):
        mention['token_span'] = self.fix_token_span(
            abs_index, mention['token_span'])
        if mention['sentence_id'] == sentence_id:
            mention['tokens'] = self.get_mention_tokens(mention)


    def write_token_ids(self):
        last_sentence_id = None
        within_sentnece_token_id = 0
        for abs_id, token in enumerate(self.tokens):

            sentence_id = token['sentence_id']
            if sentence_id != last_sentence_id:
                within_sentence_token_id = 0
            else:
                within_sentence_token_id += 1
            last_sentence_id = sentence_id

            token['abs_id'] = abs_id
            token['id'] = within_sentence_token_id


    def initialize_document(self, doc):
        self.tokens = doc['tokens']
        self.sentences = doc['sentences']


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
            'While adding a mention within a coreference chains for file %d, '
            'the tokens found for the mention did not match the '
            'Expected text.  '
            'expected "%s", but found "%s"'
            % (self.doc_num, expected_text, found_text)
        )


    def check_tokens_match(self, mention, mention_tokens):
        found_token_text = ''.join(t['text'] for t in mention_tokens)
        if not text_match_nowhite(found_token_text, mention['text']):
            self.raise_non_matching(found_token_text, mention['text'])


    def get_mention_tokens(self, mention, absolute=True):
        if absolute:
            return mention['token_span'].select_tokens(self.tokens)
        sentence = self.sentences[mention['sentence_id']]
        return mention['token_span'].select_tokens(sentence['tokens'])


    def accumulate_representative(self, representative, mention):
        """
        merges together multiple mentions
        """

        # Accumulate antecedents (not pronouns) to make the representative
        if mention['mention_type'] == 'pronoun':
            return representative

        # Begin accumulating the representative
        if representative is None:
            return self.copy_mention(mention)

        # Continue accumulating the representative
        representative['tokens'].extend(mention['tokens'])
        representative['token_span'].extend(mention['token_span'])
        representative['text'] = representative['tokens'].text()
        return representative


    def copy_mention(self, mention):

        # Most members get copied by value here.
        new_mention = parc_reader.mention.Mention(**mention)

        # But we need to ensure that the token list is copied by *value*
        # (although the underlying tokens are still copied by reference).
        new_mention['tokens'] = parc_reader.token_list.TokenList(
            mention['tokens'])

        return new_mention


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

                # Get mention tokens (they are indexed from start of sentence).
                mention_tokens = self.get_mention_tokens(
                    mention, absolute=False)

                # Ensure that we got the right tokens by checking the text.
                self.check_tokens_match(mention, mention_tokens)

                token_span = parc_reader.token_span.TokenSpan(
                    mention['token_span'])

                # Store token indices relative to the start of the document.
                token_span = tokens_2_token_span(mention_tokens, absolute=True)

                new_mention = parc_reader.mention.Mention(
                    token_span=token_span,
                    sentence_id=mention['sentence_id'],
                    tokens=mention_tokens,
                    text=mention_tokens.text(),
                    mention_type=mention['mention_type'],
                    reference=new_reference
                )

                new_reference['mentions'].append(new_mention)

                representative = self.accumulate_representative(
                    representative, new_mention)

            if representative is not None:
                new_reference['representative'] = representative


def tokens_2_token_span(tokens, absolute=True):
    token_span = parc_reader.token_span.TokenSpan()
    curr_start = None
    last_id = None
    id_field = 'abs_id' if absolute else 'id'
    for token in tokens:

        curr_id = token[id_field]

        if curr_id < 0:
            raise ValueError(
                'Token ids must be nonnegative integers: %d' % curr_id)

        if curr_id <= last_id:
            raise ValueError(
                'Tokens appear to be  out of sequence: %s' % str(tokens))

        if curr_start is None:
            curr_start = curr_id

        elif curr_id != last_id + 1:
            token_span.append((curr_start, last_id + 1))
            curr_start = curr_id

        last_id = curr_id

    if curr_start is not None:
        token_span.append((curr_start, last_id + 1))

    return token_span




class AutoIncrementer(object):
    """Provides auto-incrementing IDs"""
    def __init__(self):
        self.reset()
    def reset(self):
        self.pointer = 0
    def next(self):
        self.pointer += 1
        return self.pointer - 1


def read_sentences(path=BNP_SENTENCES_PATH):
    print "Reading BBN sentences.  This will take a minute..."
    documents = {}
    state = 'root'
    abs_token_id = AutoIncrementer()
    for i, line in enumerate(open(BNP_SENTENCES_PATH)):

        line = line.rstrip()
        #print '%d\t%s' % (i, repr(line))

        if state == 'root':

            if line[0] == '(':
                # We are starting a new document
                doc_num = parse_doc_num(line)
                state = 'in_doc'
                abs_token_id.reset()
                new_token_list = parc_reader.token_list.TokenList()
                document = {'sentences':[], 'tokens':new_token_list}
                documents[doc_num] = document

            else:
                raise ValueError(
                    'Expecting document start or end of file, but got "%s"' 
                    % line
                )

        elif state == 'in_doc':

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

                tokens = parc_reader.token_list.TokenList([
                    {
                        'id': i,                        # index within sentence
                        'abs_id': abs_token_id.next(),  # index within doc
                        'sentence_id': sentence_id, 
                        'text': t
                    }
                    for i, t in enumerate(content.lstrip().split())
                ])

                start_index = len(document['tokens'])
                document['tokens'].extend(tokens)
                end_index = len(document['tokens'])
                token_span = parc_reader.token_span.TokenSpan(
                    single_range=(start_index, end_index))

                document['sentences'].append({
                    'id': sentence_id,
                    'token_span': token_span,
                    'tokens': tokens
                })

            elif line == ')':
                state = 'root'

            else:
                raise ValueError(
                    'Expecting sentence or document end  but got "%s".' % line)

        else:
            raise ValueError('Unexpected state: "%s".' % state)

    return documents



def remove_whitespace(string):
    return WHITESPACE.sub('', string)



def text_match_nowhite(text1, text2):
    text1_nowhite = remove_whitespace(text1)
    text2_nowhite = remove_whitespace(text2)
    return text1_nowhite == text2_nowhite



def read_pronouns(path=BNP_PRONOUNS_PATH):
    print "Reading BBN pronouns.  This will take a minute..."
    state = 'root'
    documents = {}

    #print path

    for i, line in enumerate(open(path)):

        line = line.rstrip()

        #print '%d\t%s' % (i,line)

        if state == 'root':
            if line[0] == '(':
                doc_num = parse_doc_num(line)
                state = 'in_doc'
                coreferences = []
                documents[doc_num] = coreferences

            else:
                raise ValueError(
                    'Expected document start openning bracket.  '
                    'Got "%s" on line %d.' % (line, i)
                )

        elif state == 'in_doc':

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

            if line.startswith('\tAntecedent') or line.startswith('\tPronoun'):
                mention = parse_mention(line)
                if doc_num == 1591 and mention['sentence_id'] == 0:
                    correct_token_offset_error(mention)
                reference.append(mention)

            elif line == '    )':
                state = 'in_doc'
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



def correct_token_offset_error(mention):
    mention['token_span'] = parc_reader.token_span.TokenSpan([
        (start - 1, end - 1) for start, end in mention['token_span']
    ])



ARTICLE_NUM_MATCHER = re.compile('\(?WSJ(\d\d\d\d)')
def parse_doc_num(line):
    try:
        return int(ARTICLE_NUM_MATCHER.match(line).groups()[0])
    except: 
        raise ValueError('Could not parse article number.  Got "%s".' % line)



def parse_mention(line, expected_mention_type=None):

    mention_type, location_spec, text = t4k.stripped(line.split('->'))
    sentence_spec, token_range_spec = location_spec.split(':')
    sentence_id = parse_sentence_id(sentence_spec)
    token_span = parc_reader.token_span.TokenSpan(
        single_range=parse_token_range(token_range_spec))

    if expected_mention_type is not None:
        if mention_type != expected_mention_type:
            raise ValueError(
                ('Expected definition for mention type "%s".  '
                'Got "%s" instead.') % (expected_mention_type, line)
            )

    return parc_reader.mention.Mention(**{
        'mention_type': mention_type.lower(),
        'sentence_id': sentence_id,
        'token_span': token_span,
        'text': text
    })


def maybe_increment(val, insertion_point):
    if val >= insertion_point:
        return val + 1
    return val


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

