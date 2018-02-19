from collections import defaultdict
from xml.dom import minidom
from parc_reader.utils import get_spans
from parc_reader.attribution import Attribution
from corenlp_xml_reader.annotated_text import (
    AnnotatedText as CorenlpAnnotatedText, Token
)
from attribution_html_serializer import AttributionHtmlSerializer
from parc_reader.new_parc_annotated_text import (
    get_attributions, get_attributions_from_brat)
import re
from bs4 import BeautifulSoup as Soup


ROLES = {'cue', 'content', 'source'}
WHITESPACE_MATCHER = re.compile(r'\s+')

class ParcCorenlpReader(object):

    def __init__(
        self, 
        corenlp_xml=None, 
        parc_xml=None, 
        raw_txt=None,
        brat_path=None,
        corenlp_path=None,
        aida_json=None, 
        apply_offset=True,
        corenlp_options={},
        parc_options={},
        align_to_parc=None
    ):

        # Either corenlp_xml or corenlp_path should be provided
        if corenlp_xml is None:
            if corenlp_path is not None:
                corenlp_xml = open(corenlp_path).read()
            else:
                raise ValueError('Provide either corenlp_xml or corenlp_path')

        # Own the raw text
        self.raw_txt = raw_txt

        # Construct the corenlp datastructure.  
        self.core = CorenlpAnnotatedText(
            corenlp_xml, aida_json, **corenlp_options
        )

        # This is essentially a monkey patch of the corenlp object.  We take
        # it's sentences.  Add an empty placeholders the sentences and tokens
        # for the (possible) attributions that they are associated to.
        self.attributions = {}
        self.sentences = self.core.sentences
        self.tokens = self.core.tokens
        for sentence in self.sentences:
            sentence['attributions'] = set()
            for token in sentence['tokens']:
                token['attributions'] = {}

        # If a parc_xml file was provided, either as a source of attributions
        # or for the expressed purpose of alignment, adopt the tokens'
        # character offsets from parc
        align_to_parc = align_to_parc or parc_xml
        if align_to_parc:
            self.align_to_parc(align_to_parc)

        # Get attribution information from the parc file now (if provided)
        if parc_xml is not None:
            self.merge_parc(parc_xml)

        # Get attribution information from the Brat file (if provided)
        if brat_path is not None:
            self.merge_brat(brat_path)

        # Determine where paragraph breaks should go (if raw text provided)
        if self.raw_txt is not None:
            self.delineate_paragraphs()

        # Initialize an incrementing integer, used for generating new
        # attribution ids
        self.incrementing_integer = 0


    def align_to_parc(self, parc_xml):

        # Iterate through tokens adopting the start-end positions from parc
        soup = Soup(parc_xml, 'html.parser')
        zipped_tokens = zip(self.core.tokens, soup.find_all('word'))
        for core_token, parc_token_tag in zipped_tokens:
            start, stop = parc_token_tag['bytecount'].split(',')
            start, stop = int(start), int(stop)
            core_token['character_offset_begin'] = start
            core_token['character_offset_end'] = stop

        self.core.refresh_token_offsets()




    def get_attribution_html(self, attribution, resolve_pronouns=False):
        serializer = AttributionHtmlSerializer()
        return serializer.get_attribution_html(
            attribution, resolve_pronouns)


    def get_all_attribution_html(self, resolve_pronouns=False):
        serializer = AttributionHtmlSerializer()
        return serializer.serialize_attributions(
            self.attributions.values(), resolve_pronouns)


    def get_parc_xml(self, indent='  '):
        xml_dom = self.create_xml_dom()
        return xml_dom.toprettyxml(indent=indent)


    def create_xml_dom(self):

        # Make a document and a root element
        doc = minidom.Document()
        root = doc.createElement('root')
        doc.appendChild(root)

        # Make an element for every sentence tag
        gorn = 0
        word = 0
        for sentence in self.sentences:

            sentence_word = 0    # keeps track of token index w/in sentence

            # First get the top (sentence) tag (bypass the root tag)
            sentence_constituent = sentence['c_root']['c_children'][0]

            # Recursively build the sentence tag (with all constituent
            # and word tags)
            root_sentence_xml_tag = doc.createElement('SENTENCE')
            root_sentence_xml_tag.setAttribute('gorn', str(gorn))
            sentence_xml_tag, word, sentence_word = self.create_sentence_tag(
                doc, sentence_constituent, word=word, 
                sentence_word=sentence_word, gorn_trail=(), gorn=gorn
            )
            root_sentence_xml_tag.appendChild(sentence_xml_tag)
            gorn += 1

            # Append the sentence tag to the growing document
            root.appendChild(root_sentence_xml_tag)

        return doc


    def create_sentence_tag(
        self,
        doc,
        constituent,
        word=0,
        sentence_word=0,
        gorn_trail=(),
        gorn=0
    ):

        # Is this a compund constituent, or a token?
        is_token = False
        if len(constituent['c_children']) == 0:
            is_token = True

        # Create the xml tag for this constituent
        if is_token:
            element = doc.createElement('WORD')
            element.setAttribute(
                'ByteCount', '%s,%s' % (
                constituent['character_offset_begin'],
                constituent['character_offset_end'])
            )
            element.setAttribute('lemma', constituent['lemma'])
            element.setAttribute('pos', constituent['pos'])
            element.setAttribute('text', constituent['word'])
            element.setAttribute('gorn', self.gorn_str(gorn_trail, gorn))
            element.setAttribute('word', str(word))
            element.setAttribute('sentenceWord', str(sentence_word))
            word += 1
            sentence_word += 1

            # A token can be involved in multiple attributions
            for attr_id in constituent['attributions']:

                attribution = element.appendChild(
                    doc.createElement('attribution'))
                attribution.setAttribute('id', attr_id)

                # A token can have multiple roles for a given attribution
                for role in constituent['attributions'][attr_id]:
                    attribution_role = attribution.appendChild(
                        doc.createElement('attributionRole'))
                    attribution_role.setAttribute('roleValue', role)

            return element, word, sentence_word

        element = doc.createElement(constituent['c_tag'])
        element.setAttribute('gorn', self.gorn_str(gorn_trail, gorn))

        # Create the child elements
        child_gorn = 0
        for child in constituent['c_children']:
            child_elm, word, sentence_word = self.create_sentence_tag(
                doc, child, word=word, sentence_word=sentence_word,
                gorn_trail=(gorn_trail + (gorn,)), gorn=child_gorn
            )
            element.appendChild(child_elm)
            child_gorn += 1

        return element, word, sentence_word


    def gorn_str(self, gorn_trail, gorn):
        return ','.join([str(g) for g in gorn_trail + (gorn,)])


    def __str__(self):
        return self.core.__str__()


    def delineate_paragraphs(self):

        # A paragraph is just an array of CorenlpSentence objects
        self.paragraphs = []

        # Read the orignial raw text, and split it into its paragraphs
        paragraph_texts = self.raw_txt.strip().split('\n\n')

        # Collapse all whitespace out of the paragraphs.  This makes
        # aligning them to the sentences easier, because whitespace
        # does not consistently appear between tokens
        collapsed_paragraph_texts = [
            WHITESPACE_MATCHER.sub('', p) for p in paragraph_texts
        ]

        sentence_pointer = 0
        last_excess = 0
        paragraph_idx = -1
        for collapsed_paragraph in collapsed_paragraph_texts:

            # We begin by assuming the paragraph consists of one sentence
            target_length = len(collapsed_paragraph)
            current_num_sentences = 1

            # Occasionally a paragraph break occurs within what was
            # considered one sentence in PARC.  This can happen when a 
            # heading is followed by a subheading.  If this paragraph
            # helps to make up for the excess of length in the last 
            # paragraph then that's probably what happened.  Skip it, and
            # deduct its length from the excess length.
            if last_excess - target_length >= 0:
                #print 'skipping!'
                last_excess -= target_length
                continue

            # But if we run out of sentences, then there's no more 
            # paragraphs to make, so break!
            try:
                current_length = self.get_collapsed_length(sentence_pointer)
            except IndexError:
                break

            closest_length = current_length
            closest_distance = abs(target_length - current_length)
            best_num_sentences = 1

            # Continually include more sentences, until we exceed the
            # target length of the paragraph.  Keep track of how many
            # sentences gave the closest length to that of the paragraph
            while current_length <= target_length:

                # Try adding another sentence to this paragraph.
                # but if we run out of sentences, break.
                current_num_sentences += 1
                try:
                    current_length += self.get_collapsed_length(
                        sentence_pointer + current_num_sentences - 1
                    )
                except IndexError:
                    break

                # How close is the length of the paragraph with this 
                # many sentences?  If its the closest so far, record it.
                current_distance = abs(target_length - current_length)
                if current_distance < closest_distance:
                    closest_length = current_length
                    closest_distance = current_distance
                    best_num_sentences = current_num_sentences

            # Now put the correct number of sentences into the paragraph,
            # and store this paragraph in the article object's global list
            paragraph_idx += 1
            this_paragraph = []
            add_sentences = self.sentences[
                sentence_pointer : sentence_pointer + best_num_sentences
            ]
            for sentence in add_sentences:
                sentence['paragraph_idx'] = paragraph_idx
                this_paragraph.append(sentence)
            self.paragraphs.append(this_paragraph)

            # Advance the sentence pointer according to how many sentences
            # were aligned to the last paragraph
            sentence_pointer += best_num_sentences

            # If the paragraph we built was too big, it may be because
            # PARC glues multiple paragraphs together (because the 
            # "paragraphs" in the original are just sentence fragments and
            # we won't split paragraphs within sentence fragments).
            # Keep track of this so that we can skip these fragmentary 
            # "paragraphs" as needed.
            last_excess = closest_length - target_length

        # If there's sentences left over, add them to the last paragraph
        additional_sentences = self.sentences[sentence_pointer:]
        for sentence in additional_sentences:
            this_paragraph.append(sentence)
            sentence['paragraph_idx'] = paragraph_idx


    def _find_head(self, tokens):

        heads = []

        # If there is only one token, that's the head
        if len(tokens) ==  1:
            heads = [tokens[0]]

        else:

            # otherwise iterate over all the tokens to find the head
            for token in tokens:

                # if this token has no parents or children its not part
                # of the dependency tree (it's a preposition, e.g.)
                if 'parents' not in token and 'children' not in token:
                    continue

                # if this token has any parents that among the tokens list
                # it's not the head!
                try:

                    token_ids = [(t['sentence_id'], t['id']) for t in tokens]

                    has_parent_in_span = any([
                        (t[1]['sentence_id'], t[1]['id'])
                        in token_ids for t in token['parents']
                    ])

                    if has_parent_in_span:
                        relations_to_parents = [
                            t for t in token['parents'] if t[1] in tokens
                        ]
                        continue
                except KeyError:
                    pass

                # otherwise it is the head
                else:
                    heads.append(token)

        # NOTE: head may be none
        return heads


    def get_collapsed_length(self, sentence_num):
        # Get this sentence's tokens
        tokens = self.sentences[sentence_num]['tokens']
        # Concatenate them and calculate the total length
        return len(''.join([t['word'] for t in tokens]))


    def get_attribution_id(self, id_formatter):
        """
        Gets a new, unique attribution id, incrementing as much as needed for
        the id to actually be unique.
        """
        while True:
            attribution_id = self._get_attribution_id(id_formatter)
            if attribution_id not in self.attributions:
                break
        return attribution_id


    def _get_attribution_id(self, id_formatter):
        '''
        Provides an attribution id that is guaranteed to be unique
        within object instances using an incrementing integer.  The integer
        is appended onto the id_formatter.
        '''
        self.incrementing_integer += 1
        try:
            return id_formatter % (self.incrementing_integer - 1)
        except TypeError:
            return id_formatter + str(self.incrementing_integer - 1)


    def remove_attribution(self, attribution_id):
        '''
        Deletes the attribution identified by attribution_id, including
        all references from sentences, tokens, and globally
        '''
        attribution = self.attributions[attribution_id]

        # first remove the attribution from each of the tokens
        sentence_ids = set()
        tokens = (
            attribution['cue'] + attribution['content'] 
            + attribution['source']
        )
        for token in tokens:
            sentence_ids.add(token['sentence_id'])
            token['role'] = None
            token['attribution'] = None

        # Delete references to the attribution on sentences
        for sentence_id in sentence_ids:
            sentence = self.sentences[sentence_id]
            del sentence['attributions'][attribution_id]

        # Delete the global reference to the attribution
        del self.attributions[attribution_id]


    def add_attribution(
        self, 
        cue_tokens=[], 
        content_tokens=[], 
        source_tokens=[], 
        attribution_id=None,
        id_formatter=''
    ):
        '''
        Add a new attribution.  Create links from the sentences and tokens,
        involved, and make a reference on the global attributions list.

        Note that `cue_tokens`, `source_tokens`, and `content_tokens` can be
        either a list of token objects, or a list of (sentence_ID, token_ID)
        tuples.  If token objects are provided, then will be converted into
        (sentence_ID, token_ID) tuples.  This allows the token id to be looked
        up on the reader object itself. So, in case the tokens actually come
        from a different copy (different reader object) opened for the same
        article, the matching token objects from this reader will be the ones
        included in the attribution.
        '''

        # Work out the attribution id, and ensure it is in fact unique.
        if attribution_id is None:
            attribution_id = self.get_attribution_id(id_formatter)
        if attribution_id in self.attributions:
            raise ValueError(
                'The attribution_id supplied is already in use: %s'
                % attribution_id
            )

        # Make a new empty attribution, and place it on the global attributions
        new_attribution = Attribution(self, attribution_id)
        self.attributions[attribution_id] = new_attribution

        # Ensure each of the tokens involved in the attribution gets
        # a reference to the attribution and gets labelled with the 
        # correct role.  We also ensure that each sentence involved
        # in the attribution gets a reference to the attribution
        self.add_to_attribution(attribution_id, 'cue', cue_tokens)
        self.add_to_attribution(attribution_id, 'content', content_tokens)
        self.add_to_attribution(attribution_id, 'source', source_tokens)

        return attribution_id


    def resolve_token(self, token_spec):
        """
        Returns the actual token object, and the sentence that contains it
        based on the ``token_spec``.  The token spec can either be a token 
        object itself, or a (sentnece_id, token_id) pair.
        """

        # Get the sentence_id and token id, regardless of whether an actual
        # token object was passed
        if isinstance(token_spec, tuple):
            sentence_id, token_id = token_spec
        elif isinstance(token_spec, Token):
            sentence_id, token_id = token_spec['sentence_id'], token_spec['id']

        # Look up the token on this reader
        token = self.sentences[sentence_id]['tokens'][token_id]

        # Return the sentence id and the token object
        return sentence_id, token


    # TODO: does this prevent overlapping attibutions, like the way
    #    `add_attribution` does?
    def add_to_attribution(self, attribution_id, role, tokens):

        # Get the attribution
        attribution = self.attributions[attribution_id]

        # Resolve the tokens, ensuring that they are tokens belonging to
        # this reader, and not some other reader.
        resolved_tokens = []
        sentence_ids = set()
        for token in tokens:

            sentence_id, token = self.resolve_token(token)
            attribution[role].append(token)
            sentence_ids.add(sentence_id)

            try:
                token['attributions'][attribution_id].add(role)
            except KeyError:
                token['attributions'][attribution_id] = set([role])

        for sentence in (self.sentences[sid] for sid in sentence_ids):
            sentence['attributions'].add(attribution_id)


    def map_byte_range_to_tokens(self, start, end):
        """
        Given a start byte and end byte, collect the corresponding list of
        (sentence_id, token_id) tuples.
        """
        pointer = start
        tokens = []
        while pointer < end:

            # Get the next token.  If we turn up nothing, move the pointer
            # forward one byte.
            try:
                cur_token = self.core.tokens_by_offset[pointer]
            except KeyError:
                pointer += 1
                continue

            # Add the found token to the list, and advance to pointer to the
            # end of that token
            tokens.append(cur_token)
            pointer = cur_token['character_offset_end']

        return tokens


    def map_byte_range_to_token_ids(self, start, end):
        tokens = self.map_byte_range_to_tokens(start, end)
        return [(t['sentence_id'], t['id']) for t in tokens]
        

    def merge_brat(self, brat_path):
        """
        This merges information from CoreNLP with information from the
        BRAT annotations, while assuming that they have identical 
        byte offsets for the words.
        """
        attributions = self.get_brat_attributions(open(brat_path).read())
        self.merge(attributions)


    def get_brat_attributions(self, brat_text):
        # Get a representation of the annotations in the brat file
        attribution_specs = get_attributions_from_brat(brat_text)

        # Convert the byte ranges in the attribution specs into token_id lists
        attributions = {}
        for attr_label, attr_spec in attribution_specs.iteritems():
            new_attribution = {'sentences':set()}
            attributions[attr_label] = new_attribution
            for role in attr_spec:
                new_attribution[role] = []
                for range_spec in attr_spec[role]:
                    token_ids = self.map_byte_range_to_token_ids(*range_spec)
                    sentence_ids = [sid for sid, tid in token_ids]
                    new_attribution[role].extend(token_ids)
                    new_attribution['sentences'].update(sentence_ids)

        return attributions


    def merge_parc(self, parc_xml):
        attributions = get_attributions(parc_xml)
        self.merge(attributions)


    def merge(self, attributions):
        '''
        This merges information from CoreNLP with information from the
        Parc annotations, while assuming that they have identical 
        tokenization and sentence spliting (which makes alignment trivial).
        '''
        for attr_id, attribution_spec in attributions.iteritems():

            # Create an attribution object that will store references to the
            # actual tokens involved.
            attribution = Attribution(self, attr_id)
            self.attributions[attr_id] = attribution

            # Associate sentences involved with this attribution.
            for sentence_id in attribution_spec['sentences']:
                self.sentences[sentence_id]['attributions'].add(attr_id)

            # Note onto the token it's role(s) in this attribution
            # and make references from the attribution to the tokens.
            for role in ROLES:

                # Currently permittin missing roles.  Theoretically only the
                # source can be missing in a valid attribution relation.
                if role not in attribution_spec: continue

                for sentence_id, token_id in attribution_spec[role]:
                    token = self.sentences[sentence_id]['tokens'][token_id]
                    try:
                        token['attributions'][attr_id].add(role)
                    except KeyError:
                        token['attributions'][attr_id] = set([role])
                    attribution[role].append(token)

