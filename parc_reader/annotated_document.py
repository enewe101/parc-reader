import re
import parc_reader

WHITESPACE = re.compile('\s+')
class AnnotatedDocument(object):

    def __init__(self,
        tokens=None,
        sentences=None,
        annotations=None,
        doc_id=None,
    ):

        self.doc_id = doc_id
        self.annotations = annotations or {}
        self.tokens = parc_reader.token_list.TokenList(tokens or [])

        self.sentences = []
        if sentences is not None:
            for sentence in sentences:
                self.add_sentence(sentence)

        #self.initialize_document(doc)
        #self.initialize_coreferences(coreferences)
        #self.initialize_entity_types(entity_types)
        #self.validate_mention_tokens()
        #self.initialize_attributions(attributions)


    def add_token(self, token):
        abs_id = len(self.tokens)
        token['abs_id'] = abs_id
        self.tokens.append(token)
        return abs_id


    def add_sentence(self, sentence):
        sentence_id = len(self.sentences)
        sentence = parc_reader.spans.Span(sentence, absolute=True)
        sentence['id'] = sentence_id
        self.sentences.append(sentence)
        


    def get_sentence_tokens(self, sentence_id):
        if self.sentences is None:
            raise ValueError(
                'This annotated document has no sentence information')
        return self.get_tokens_abs(self.sentences[sentence_id])


    def get_tokens_abs(self, span):
        span = self.span_or_token_span(span)
        selected = parc_reader.token_list.TokenList()
        for _, start, end in span:
            selected.extend(self.tokens[start:end])
        return selected


    def get_tokens(self, span):

        # We can only do this if the document has sentences defined
        if self.sentences is None:
            raise ValueError(
                'This annotated document has no sentence information')

        span = self.span_or_token_span(span)
        selected = parc_reader.token_list.TokenList()
        for sentence_id, start, stop in span:
            selected.extend(self.get_sentence_tokens(sentence_id)[start:stop])
        return selected


    def span_or_token_span(self, span):
        # Accept both spans and token_spans
        try:
            return span['token_span']
        except TypeError:
            return span


    def relativize(self, token_ranges):
        print 'trying to process:', token_ranges
        new_token_ranges = []

        for token_range in token_ranges:

            dummy_sentence_id, start, end = token_range
            if dummy_sentence_id is not None:
                ValueError('Cannot relativize token range: already relative.')

            successfully_relativized_range = False

            for sentence_id, sentence in enumerate(self.sentences):

                _, sent_start, sent_end = sentence['token_span'][0]
                print 'comparing to:', sentence['token_span'][0]

                if start >= sent_start and start < sent_end:
                    if end <= sent_end:
                        new_token_ranges.append((
                            sentence_id,
                            start - sent_start,
                            end - sent_start
                        ))
                        successfully_relativized_range = True
                    else:
                        new_token_ranges.extend(self.relativize([
                            (None, start, sent_end), (None, sent_end, end)
                        ]))
                        successfully_relativized_range = True

                if sent_start >= end:
                    break

            if not successfully_relativized_range:
                raise ValueError(
                    'Could not relativize %s' % str(token_range))

        return new_token_ranges


    def absolutize(self, token_ranges):
        new_token_ranges = []

        for token_range in token_ranges:

            sentence_id, start, end = token_range
            if not isinstance(sentence_id, int):
                ValueError('Cannot relativize token range: already relative.')

            sentence = self.sentences[sentence_id]
            _, sent_start, sent_end = sentence['token_span'][0]
            new_token_ranges.append((
                None, start + sent_start, end + sent_start))

        return new_token_ranges


    def initialize_attributions(self, attributions):
        paired_sentences = zip(attributions['sentences'], self.sentences)
        for new_sentence, existing_sentence in paired_sentences:
            new_text = ' '.join([t['text'] for t in new_sentence['tokens']])
            existing_text = existing_sentence['tokens'].text()
            if not text_match_nowhite(new_text, existing_text):

                print self.doc_id
                print existing_sentence['id']
                print new_text
                print existing_text

                print '\n\t' + '-'*30 + '\n'


    def merge_tokens(self, other, copy_token_fields, copy_annotations):

        # Copy over annotations
        for annotation in copy_annotations:
            self.annotations[annotation] = other.annotations[annotation]

        token_pointer = 0
        for other_token in other.tokens:

            self_token = self.tokens[token_pointer]
            self_text, other_text = self_token['text'], other_token['text']

            print self_text, other_text

            # Skip the stray apostraphe in doc 63.
            if self.doc_id == 63:
                if self_token['abs_id'] == 291:
                    continue

            # If they are the same token, merge the annotations
            if self_text == other_text:
                self_token.update(t4k.select(other_token, copy_token_fields))

            # If the new token is a subset of the existing token, split
            # the existing token
            elif self_text.startswith(other_text):
                print (
                    '\t\tdoc #%d, token %d, splitting "%s" into "%s" and "%s"'
                    % (
                        self.doc_id, self_token['abs_id'], self_text,
                        other_text, self_text.split(other_text, 1)[1]
                    )
                )
                self_token, remainder = self.split_token(self_token, other_text)
                self_token.update(t4k.select(other_token, copy_token_fields))

            else:
                raise ValueError(
                    '\t\tdoc #%d, token %d, expecting "%s" got "%s"'
                    % (self.doc_id,self_token['abs_id'],self_text,other_text)
                )

            token_pointer += 1


    def split_token(self, token, partial_text):

        abs_index = token['abs_id'] + 1
        remainder = token['text'].split(partial_text, 1)[1]
        token['text'] = partial_text
        remainder_token = dict(token, text=remainder)
        self.insert_token(abs_index, remainder_token)

        return token, remainder_token


    def insert_token(self, abs_index, token):

        # Insert the new token in the global tokens list
        self.tokens.insert(abs_index, token)

        # Rewrite all the token ids to restore unique compact incrementing ids
        self.write_token_ids()

        insertion_point = [
            abs_index,
            token.get('sentence_id', None),
            token.get('id', None)
        ]

        # Posibly adjust sentences
        if self.sentences:
            for sentence in self.sentences:
                sentence.accomodate_inserted_token(*insertion_point)

        # Adjust annotations
        for annotation_type in self.annotations:
            for annotation in self.annotations[annotation_type].values():
                annotation.accomodate_inserted_token(*insertion_point)


    #def validate_mention_tokens(self):

    #    for coreference_id, coreference in self.coreferences.items():
    #        if 'representative' in coreference:
    #            rep = coreference['representative']
    #            expected_text = rep['text']
    #            found_text = self.get_mention_tokens(rep).text()

    #            if not text_match_nowhite(expected_text, found_text):
    #                raise ValueError(
    #                    'Non-matching text in doc# %d, coreference# %d, '
    #                    'mention# [rep]. Expected "%s", found "%s".'
    #                    % (self.doc_id,coreference_id,expected_text,found_text)
    #                )

    #        for mention_id, mention in enumerate(coreference['mentions']):
    #            expected_text = mention['text']
    #            found_text = self.get_mention_tokens(mention).text()

    #            if not text_match_nowhite(expected_text, found_text):
    #                raise ValueError(
    #                    'Non-matching text in doc# %d, coreference# %d, '
    #                    'mention# %d. Expected "%s", found "%s".'
    #                    % (
    #                        self.doc_id,coreference_id,mention_id,
    #                        expected_text,found_text
    #                    )
    #                )


    #def fix_sentence_indices(self, abs_index):
    #    for sentence in self.sentences:
    #        sentence['token_span'] = self.fix_token_span(
    #            abs_index, sentence['token_span'])


    #def fix_mentions_tokens(self, abs_index, sentence_id):
    #    for coreference in self.coreferences.values():
    #        if 'representative' in coreference:
    #            self.fix_mention_tokens(
    #                abs_index, sentence_id, coreference['representative'])
    #        for mention in coreference['mentions']:
    #            self.fix_mention_tokens(abs_index, sentence_id, mention)


    #def fix_token_span(self, abs_index, token_span):
    #    return parc_reader.spans.TokenSpan([
    #        (maybe_increment(start,abs_index), maybe_increment(stop,abs_index))
    #        for start, stop in token_span
    #    ])


    #def fix_mention_tokens(self, abs_index, sentence_id, mention):
    #    mention['token_span'] = self.fix_token_span(
    #        abs_index, mention['token_span'])
    #    if mention['sentence_id'] == sentence_id:
    #        mention['tokens'] = self.get_mention_tokens(mention)


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


    #def initialize_coreferences(self, coreferences=None):
    #    self.next_coreferences_id = 0
    #    self.coreferences = {}
    #    self.add_coreferences(coreferences)


    #def validate_text_match(self, mention, mention_tokens):
    #    # Check that tokens we found contain the text we expected
    #    # (ignoring differences in whitespace).
    #    found_mention_text = ''.join(t['text'] for t in mention_tokens)
    #    found_text_no_white = WHITESPACE.sub('', found_mention_text)
    #    expected_text_no_white = WHITESPACE.sub('', mention['text'])
    #    if found_text_no_white != expected_text_no_white:
    #        raise ValueError(
    #            'While adding a mention within a coreference chains, '
    #            'the tokens found for the mention did not match the '
    #            'Expected text.  '
    #            'expected "%s", but found "%s"'
    #            % (expected_text_no_white, found_text_no_white)
    #        )



    #def get_mention_tokens(self, mention, absolute=True):
    #    if absolute:
    #        return mention['token_span'].select_tokens(self.tokens)
    #    sentence = self.sentences[mention['sentence_id']]
    #    return mention['token_span'].select_tokens(sentence['tokens'])

