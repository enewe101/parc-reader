import parc_reader
import os
import re
import t4k
import copy
import bs4
from collections import defaultdict, Counter


BNP_PRONOUNS_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.pron')
BNP_SENTENCES_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.sent')
BBN_ENTITY_TYPES_DIR = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'WSJtypes-subtypes')
PROPBANK_PATH = os.path.join(
    parc_reader.SETTINGS.PROPBANK_DIR, 'data', 'vloc.txt')

def read_bnp_pronoun_dataset(
    subset='all',
    skip=None,
    limit=None
):

    # Read in coreference, entity, and attribution annotations from disk
    coreference_annotated_docs = read_coreference_annotations(
        subset=subset, skip=skip, limit=limit)
    entity_annotated_docs = read_bbn_entity_types(limit=limit)
    attributions_by_doc = parc_reader.parc_dataset.read_all_parc_files(
        subset=subset, skip=skip, limit=limit)
    propbank_verbs_by_doc = read_propbank_verbs()

    # Prepare to iterate over all docs, combine the three anotation sources for
    # each, and save them in a dictionary.
    merged_annotated_docs = {}
    seen_docs = set()
    expected_docs = list(
        parc_reader.parc_dataset.iter_doc_num(subset, skip, limit))
    for doc_id in expected_docs:

        # Annotations could be missing for any given doc.  Just step over it.
        try:
            coreference_annotated_doc = coreference_annotated_docs[doc_id]
            attribution_annotated_doc = attributions_by_doc[doc_id]
            entity_annotated_doc = entity_annotated_docs[doc_id]
            propbank_verbs = propbank_verbs_by_doc[doc_id]
        except KeyError:
            print 'Could not create doc_id %d' % doc_id
            continue

        # Merge entity-type annotations with coreference annotations.
        coreference_annotated_doc.merge_tokens(
            entity_annotated_doc,
            copy_token_fields=['entity'],
            copy_annotations=['entities'],
            verbose=True
        )

        # Merge the parc-derived annotations (attribution, constituency parse,
        # and part-of-speech (POS)) with the other annotations.
        attribution_annotated_doc.merge_tokens(
            coreference_annotated_doc,
            copy_token_fields=['entity'],
            copy_annotations=['entities', 'coreferences']
        )

        merge_propbank_verbs(attribution_annotated_doc, propbank_verbs)

        merged_annotated_docs[doc_id] = attribution_annotated_doc
        seen_docs.add(doc_id)

    return merged_annotated_docs



def merge_propbank_verbs(annotated_doc, propbank_verbs):
    """
    Incoroporate propbank_verb annotations into annotated_doc.

    Find tokens in annotated_doc that correspond to propbank verbs; add an
    attribute to those tokens, and place a list of all propbank verbs in the
    documents annotations dictionary.

    This works by mutating annotated_doc.
    """
    propbank_verb_tokens = {}
    for verb_id, (sentence_id, token_id, lemma) in enumerate(propbank_verbs):
        token = find_nearest_matching_token(
            annotated_doc, sentence_id, token_id, lemma)

        # It may not be possible to find a match.  Just keep going if so.
        if token is None: 
            continue

        token['is_propbank_verb'] = True
        token_range = (token['sentence_id'], token['id'], token['id'] + 1)
        propbank_verb_tokens[verb_id] = (parc_reader.spans.Span({
            'lemma': lemma,
            'token_span': [token_range]
        }))

    annotated_doc.annotations['propbank_verbs'] = propbank_verb_tokens


# TODO: compress this functionality.
MAX_TOKEN_EXACT_MATCH_DISTANCE = 50
MAX_TOKEN_NEAR_MATCH_DISTANCE = 10
def find_nearest_matching_token(annotated_doc, sentence_id, token_id, lemma):
    """
    Look for a token having `lemma`, near `(sentence_id, token_id)` in 
    `annotated_doc`.  First, look for an exact match.  If none is found, accept
    the closest match (in terms of number of characters in common overlap).
    """
    try:
        return find_nearest_exact_matching_token(
            annotated_doc, sentence_id, token_id, lemma)
    except ValueError:
        return find_closest_near_matching_token(
            annotated_doc, sentence_id, token_id, lemma)


def character_overlap(str1, str2):
    counts1, counts2 = Counter(str1), Counter(str2)
    overlap_amount = 0
    for c in counts1:
        overlap_amount += min(counts1[c], counts2[c])
    return overlap_amount / float(max(len(str1), len(str2)))


def find_nearest_exact_matching_token(
    annotated_doc,
    sentence_id,
    token_id,
    lemma
):

    # Absolutize the location that we're expecting the token
    absolute_token_id = annotated_doc.absolutize(
        [(sentence_id, token_id, token_id+1)]
    )[0][1]

    token_found = False
    distance = 0
    while not token_found and distance <= MAX_TOKEN_EXACT_MATCH_DISTANCE:

        if distance == 6:
            print annotated_doc.doc_id
            print lemma
            print annotated_doc.get_sentence_tokens(sentence_id).text()
        try:
            check_token_id = absolute_token_id + distance
            found_lemma = annotated_doc.tokens[check_token_id]['lemma']
            if parc_reader.annotated_document.is_same_token(lemma, found_lemma):
                print 'found at +%d' % check_token_id
                return annotated_doc.tokens[check_token_id]
        except IndexError:
            pass

        check_token_id = absolute_token_id - distance
        if check_token_id >= 0:
            try:
                found_lemma = annotated_doc.tokens[check_token_id]['lemma']
                is_same_token = parc_reader.annotated_document.is_same_token(
                    lemma, found_lemma)
                if is_same_token:
                    print 'found at +%d' % check_token_id
                    return annotated_doc.tokens[check_token_id]
            except IndexError:
                pass

        distance += 1

    sentence_text = annotated_doc.get_sentence_tokens(sentence_id).text()
    sentence_lemmas = ' '.join([
        t['lemma'] for t in 
        annotated_doc.get_sentence_tokens(sentence_id)
    ])
 
    raise ValueError(
        'Could not find a token with lemma "%s" near token %d in sentence %d.'
        '\n\n"%s"'
        % (lemma, token_id, sentence_id, sentence_lemmas)
    )

def find_closest_near_matching_token(
    annotated_doc,
    sentence_id,
    token_id,
    lemma
):

    # Absolutize the location that we're expecting the token
    absolute_token_id = annotated_doc.absolutize(
        [(sentence_id, token_id, token_id+1)]
    )[0][1]

    distance = 0
    max_overlap = t4k.Max()
    for distance in range(MAX_TOKEN_NEAR_MATCH_DISTANCE+1):

        try:
            check_token_id = absolute_token_id + distance
            check_token = annotated_doc.tokens[check_token_id]
            if check_token['pos'].startswith('VB'):
                found_lemma = check_token['lemma']
                overlap_amount = character_overlap(lemma, found_lemma)
                max_overlap.add(overlap_amount, check_token_id)
        except IndexError:
            pass

        check_token_id = absolute_token_id - distance
        if check_token_id >= 0:
            check_token = annotated_doc.tokens[check_token_id]
            if check_token['pos'].startswith('VB'):
                found_lemma = annotated_doc.tokens[check_token_id]['lemma']
                overlap_amount = character_overlap(lemma, found_lemma)
                max_overlap.add(overlap_amount, check_token_id)

    sentence_lemmas = ' '.join([
        t['lemma'] for t in 
        annotated_doc.get_sentence_tokens(sentence_id)
    ])

    max_overlap_amount, max_overlap_token_id = max_overlap.get()

    # Handle the case where there weren't even any candidates among the tokens
    # searched.
    if max_overlap_token_id is None:
        return None

    token = annotated_doc.tokens[max_overlap_token_id]
    central_token = annotated_doc.tokens[absolute_token_id]
    print central_token
    print ('found max overlap: %.2f %s %s %s: \n\n%s' % (
        max_overlap_amount, lemma, central_token['lemma'],
        token['lemma'], sentence_lemmas
    ))
    return token



def read_propbank_verbs(path=PROPBANK_PATH):

    propbank_verbs_by_doc = defaultdict(list)
    for line in t4k.trimmed_nonblank(open(path)):
        doc_id, sentence_id, token_id, lemma = parse_propbank_line(line)
        propbank_verbs_by_doc[doc_id].append((sentence_id, token_id, lemma))

    return propbank_verbs_by_doc



PROPBANK_LINE_PARSER = re.compile(
    'wsj/\d\d/wsj_(\d\d\d\d).mrg (\d+) (\d+) (\w+)')
def parse_propbank_line(line):
    matched_fields = PROPBANK_LINE_PARSER.match(line).groups()
    doc_id, sentence_id, token_id, lemma = matched_fields
    doc_id, sentence_id, token_id = int(doc_id), int(sentence_id), int(token_id)
    return doc_id, sentence_id, token_id, lemma


def make_coreference_annotated_text(
    tokens,
    sentences,
    coreferences,
    mentions,
    doc_id
):

    annotated_doc = parc_reader.annotated_document.AnnotatedDocument(
        tokens, sentences, 
        {'coreferences':coreferences, 'mentions': mentions},
        doc_id=doc_id
    )

    # Link tokens to any mentions in which they participate
    for mention_id, mention in mentions.items():
        for token in annotated_doc.get_tokens(mention['token_span']):
            try:
                token['mentions'].append(mention['id'])
            except KeyError:
                token['mentions'] = [mention['id']]

        verify_mention_tokens(mention, annotated_doc)

    return annotated_doc


def verify_mention_tokens(mention, doc):
    expected_text = mention['text']
    found_text = doc.get_tokens(mention['token_span']).text()
    assert_text_match(expected_text, found_text)




def read_bbn_entity_types(entity_types_path=BBN_ENTITY_TYPES_DIR, limit=None):
    print "Reading BBN entity types.  This will take a minute..."
    annotated_docs = {}
    for path in t4k.ls(entity_types_path):

        annotated_docs_to_add, hit_limit = parse_bbn_entity_types_file(
            open(path).read(), limit)
        annotated_docs.update(annotated_docs_to_add)

        # Stop if we hit the limit
        if hit_limit:
            return annotated_docs

        # Can stop early for debugging purposes
        #doc_id = max(annotated_docs.keys())
        #if limit is not None and doc_id == limit:
        #    return annotated_docs

    return annotated_docs



def parse_bbn_entity_types_file(xml_string, limit=None):
    xml_string = xml_string.replace(
        'vic<ENAMEX TYPE="PER_DESC">e pres</ENAMEX>ident',
        '<ENAMEX TYPE="PER_DESC">vice president</ENAMEX>'
    )
    xml_tree = bs4.BeautifulSoup(xml_string, 'xml')
    annotated_docs = {}
    hit_limit = False
    for doc_tag in xml_tree.find_all('DOC'):
        doc = parse_entity_type_doc(doc_tag)
        if limit is not None and doc.doc_id >= limit:
            hit_limit = True
            return annotated_docs, hit_limit
        annotated_docs[doc.doc_id] = doc

    return annotated_docs, hit_limit



def parse_entity_type_doc(doc_tag):
    doc_id = parse_doc_id(doc_tag.find('DOCNO').text.strip())
    tokens = []
    entities = {}

    for child in doc_tag.contents:

        if child.name == 'DOCNO':
            continue

        if is_text_node(child):
            for text in child.strip().split():
                token = {
                    'text':text,
                    'abs_id': len(tokens),
                    'entity': None
                }
                tokens.append(token)

        else:
            entity = parc_reader.spans.Span({
                'id': len(entities),
                'entity_type': tuple([child.name] + child['TYPE'].split(':')),
                'text': child.text.strip()
            }, absolute=True)
            entities[entity['id']] = entity

            token_ids = []
            for text in entity['text'].split():
                token = {
                    'text': text, 
                    'entity': entity['id'],
                    'abs_id': len(tokens),
                }
                tokens.append(token)
                token_ids.append(token['abs_id'])

            min_id, max_id = min(token_ids), max(token_ids)
            entity.add_token_range((min_id, max_id+1))

    return parc_reader.annotated_document.AnnotatedDocument(
        tokens=tokens, annotations={'entities':entities}, doc_id=doc_id)



def is_text_node(element):
    """
    You can tell that an element is a text node if it has no tag *name*.
    """
    return element.name is None





def tokens_2_token_span(tokens, absolute=True):
    token_span = parc_reader.spans.TokenSpan()
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


def read_coreference_sentences_from_disk(path=BNP_SENTENCES_PATH, limit=None):
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
                doc_id = parse_doc_id(line)

                # Can stop early
                if limit is not None and doc_id >= limit:
                    return documents

                state = 'in_doc'
                abs_token_id.reset()
                new_token_list = parc_reader.token_list.TokenList()
                document = {'sentences':[], 'tokens':new_token_list}
                documents[doc_id] = document

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

                start = len(document['tokens'])
                document['tokens'].extend(tokens)
                end = len(document['tokens'])

                document['sentences'].append(parc_reader.spans.Span({
                    'id': sentence_id,
                    'token_span': [(None, start, end)]
                }, absolute=True))

            elif line == ')':
                state = 'root'

            else:
                raise ValueError(
                    'Expecting sentence or document end  but got "%s".' % line)

        else:
            raise ValueError('Unexpected state: "%s".' % state)

    return documents


WHITESPACE = re.compile('\s+')
def remove_whitespace(string):
    return WHITESPACE.sub('', string)


def text_match_nowhite(text1, text2):
    text1_nowhite = remove_whitespace(text1)
    text2_nowhite = remove_whitespace(text2)
    return text1_nowhite == text2_nowhite


def read_coreference_annotations(
    path=BNP_PRONOUNS_PATH,
    subset='all',
    skip=None,
    limit=None
):
    coref_sentences_by_doc = read_coreference_sentences_from_disk(limit=limit)
    coref_info_by_doc = read_coreference_information_from_disk(limit=limit)

    coreference_annotated_docs = {}
    for doc_id in parc_reader.parc_dataset.iter_doc_num(subset, skip, limit):

        try:
            sentences = coref_sentences_by_doc[doc_id]
            coreferences, mentions = coref_info_by_doc[doc_id]
        except KeyError:
            continue

        # Build the coreference-annotated document from the coreference
        # information that has been loaded from disk
        coreference_annotated_docs[doc_id] = make_coreference_annotated_text(
            sentences['tokens'],
            sentences['sentences'],
            coreferences,
            mentions,
            doc_id
        )

    return coreference_annotated_docs


def read_coreference_information_from_disk(path=BNP_PRONOUNS_PATH, limit=None):
    parsed_docs = parse_coreference_annotations(open(path).read(), limit)
    annotations_by_doc = assemble_all_coreference_annotations(parsed_docs)
    return annotations_by_doc



def assemble_all_coreference_annotations(parsed_docs):
    return {
        doc_id : assemble_doc_coreference_annotations(coreference_specs)
        for doc_id, coreference_specs in parsed_docs.items()
    }



def assemble_doc_coreference_annotations(coreference_specs):

    coreferences = {}
    mentions = {}

    # We'll need a sorting function for later...
    def get_mention_sort_key(mention_id):
        return mentions[mention_id]['token_span'][0]

    for coreference_spec in coreference_specs:

        coreference_id = len(coreferences)
        coreference = Coreference({
            'id': coreference_id,
            'pronouns': [],
            'antecedents': [],
        })
        coreferences[coreference_id] = coreference

        for mention in coreference_spec:
            mention_id = len(mentions)
            mention['id'] = mention_id
            mention['coreference_id'] = coreference_id
            mentions[mention_id] = mention
            coreference[mention['mention_type']+'s'].append(mention_id)

        coreference['pronouns'].sort(key=get_mention_sort_key)
        coreference['antecedents'].sort(key=get_mention_sort_key)

        representative = accumulate_representative(
            mentions, coreference['antecedents']
        )
        if representative is not None:
            representative_id = len(mentions)
            representative['id'] = representative_id
            mentions[representative_id] = representative
            coreference['representative'] = representative_id
        else:
            coreference['representative'] = None


    return coreferences, mentions


class Coreference(dict):
    def accomodate_inserted_token(self, *insertion_point):
        pass


def accumulate_representative(mentions, antecedent_ids):
    """
    merges together multiple antecedents into one representative mention.
    """

    representative = None
    for antecedent_id in antecedent_ids:
        antecedent = mentions[antecedent_id]

        if representative is None:
            representative = parc_reader.spans.Span(
                antecedent, mention_type='representative')

        else:
            representative.add_token_ranges(antecedent['token_span'])
            representative['text'] += ' ' + antecedent['text']

    return representative



def assert_text_match(expected_text, found_text):
    if not text_match_nowhite(expected_text, found_text):
        raise ValueError(
            'While adding a mention within a coreference chains for file %d, '
            'the tokens found for the mention did not match the '
            'Expected text.  '
            'expected "%s", but found "%s"'
            % (expected_text, found_text)
        )



def parse_coreference_annotations(text_to_parse, limit=None):
    print "Reading BBN pronouns.  This will take a minute..."
    state = 'root'
    documents = {}

    for i, line in enumerate(t4k.skip_blank(text_to_parse.split('\n'))):

        line = line.rstrip()

        if state == 'root':

            if line[0] == '(':
                doc_id = parse_doc_id(line)

                # Can stop early for debugging purposes
                if limit is not None and doc_id >= limit:
                    return documents

                state = 'in_doc'
                coreferences = []
                documents[doc_id] = coreferences

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
                state = 'in_coreference'
                coreference = []
                coreferences.append(coreference)

            else:
                raise ValueError(
                    'Expected coreference chain start or document end.  '
                    'Got "%s" on line %d.' % (line, i)
                )

        elif state == 'in_coreference':

            if line.startswith('\tAntecedent') or line.startswith('\tPronoun'):
                mention = parse_mention(line)
                if doc_id == 1591 and mention['sentence_id'] == 0:
                    correct_token_offset_error(mention)
                coreference.append(mention)

            elif line == '    )':
                state = 'in_doc'
                coreference = None

            else:
                raise ValueError(
                    'Expected antecedent or pronoun definition or end of '
                    'coreference chain.  Got "%s" on line %d.' % (line, i)
                )

        else:
            raise ValueError('Unexpected state: %s.' % state)

    if state != 'root':
        raise ValueError(
            'Unexpected end of file.  Expected to be at root state, '
            'but currently in "%s" state; on line %d.' % (state, i)
        )

    return documents



def correct_token_offset_error(mention):
    mention['token_span'] = parc_reader.spans.TokenSpan([
        (sent_id, start - 1, end - 1) 
        for sent_id, start, end in mention['token_span']
    ])



ARTICLE_NUM_MATCHER = re.compile('\(?WSJ(\d\d\d\d)')
def parse_doc_id(line):
    try:
        return int(ARTICLE_NUM_MATCHER.match(line).groups()[0])
    except: 
        raise ValueError('Could not parse article number.  Got "%s".' % line)



def parse_mention(line):

    mention_type, location_spec, text = t4k.stripped(line.split('->'))
    sentence_id, start, stop = parse_location_spec(location_spec)

    return parc_reader.spans.Span(
        mention_type=mention_type.lower(),
        sentence_id=sentence_id,
        token_span=[(sentence_id, start, stop)],
        text=text
    )


def maybe_increment(val, insertion_point):
    if val >= insertion_point:
        return val + 1
    return val



def parse_location_spec(location_spec):
    sentence_spec, token_range_spec = location_spec.split(':')
    sentence_id = parse_sentence_id(sentence_spec)
    start, stop = parse_token_range(token_range_spec)
    return sentence_id, start, stop


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

