import parc_reader
import os
import re
import t4k

BNP_PRONOUNS_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.pron')
BNP_SENTENCES_PATH = os.path.join(
    parc_reader.SETTINGS.BNP_DIR, 'data', 'BBN-wsj-pronouns', 'WSJ.sent')


def read_bnp_sentences(path=BNP_SENTENCES_PATH):
    documents = {}
    state = 'root'
    for i, line in enumerate(open(BNP_SENTENCES_PATH)):

        line = line.rstrip()
        #print '%d\t%s' % (i, repr(line))

        if state == 'root':

            if line[0] == '(':
                article_num = parse_article_num(line)
                state = 'in_article'
                document = {'sentences':[], 'tokens':[]}
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
                if sentence_id != len(document['sentences']) + 1:
                    raise ValueError(
                        'Expecting sentence %d but got %d' 
                        % (len(document['sentences']), sentence_id)
                    )

                tokens = [{'text':t} for t in content.lstrip().split()]

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
 


def read_bnp_pronoun_dataset(
    pronouns_path=BNP_PRONOUNS_PATH,
    sentences_path=BNP_SENTENCES_PATH
):

    documents = read_bnp_sentences()
    pronoun_annotations = read_bnp_pronouns()

    seen_articles = set()
    for article_num in documents:
        sent_doc = documents[article_num]
        pronoun_doc = pronoun_annotations[article_num]
        seen_articles.add(article_num)

        #
        # LEFT OFF
        #
        # iterate through coreference chains of the pronoun doc
        # and use their indices to attach pronoun information to 
        # the sent_doc's tokens.
        #

    unseen_articles = set(pronoun_annotations.keys()) - seen_articles
    if len(unseen_articles) > 0:
        raise ValueError(
            'Some articles were not seen: %s.' % ', '.join(unseen_articles)
        )





def read_bnp_pronouns(path=BNP_PRONOUNS_PATH):

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
                coreference_chains = []
                documents[article_num] = coreference_chains

            else:
                raise ValueError(
                    'Expected document start openning bracket.  '
                    'Got "%s" on line %d.' % (line, i)
                )

        elif state == 'in_article':

            if line[0] == ')':
                coreference_chains = None
                state = 'root'

            elif line == '    (':
                state = 'in_coreference_chain'
                coreference_chain = []
                coreference_chains.append(coreference_chain)

            else:
                raise ValueError(
                    'Expected coreference chain start or document end.  '
                    'Got "%s" on line %d.' % (line, i)
                )

        elif state == 'in_coreference_chain':

            if line.startswith('\tAntecedent'):
                coreference_chain.append(parse_entity(line))

            elif line.startswith('\tPronoun'):
                coreference_chain.append(parse_entity(line))

            elif line == '    )':
                state = 'in_article'
                coreference_chain = None

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


def parse_entity(line, expected_entity_type=None):

    entity_type, location_spec, token = t4k.stripped(line.split('->'))
    sentence_spec, character_range_spec = location_spec.split(':')
    sentence_id = parse_sentence_id(sentence_spec)
    start_offset, end_offset = parse_character_range(character_range_spec)

    if expected_entity_type is not None:
        if entity_type != expected_entity_type:
            raise ValueError(
                ('Expected definition for entity type "%s".  '
                'Got "%s" instead.') % (expected_entity_type, line)
            )

    return {
        'type': entity_type.lower(),
        'sentence': sentence_id,
        'start_offset': start_offset,
        'end_offset': end_offset, 
        'token': token
    }


SENTENCE_ID_MATCHER = re.compile('S(\d+)')
def parse_sentence_id(sentence_spec):
    return int(SENTENCE_ID_MATCHER.match(sentence_spec).groups()[0])

def parse_character_range(character_range_spec):
    offset1, offset2 = character_range_spec.split('-')
    return int(offset1), int(offset2)


