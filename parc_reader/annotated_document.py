import re
import parc_reader
import t4k


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


    def add_token(self, token):
        abs_id = len(self.tokens)
        token['abs_id'] = abs_id
        self.tokens.append(token)
        return abs_id


    def add_sentence(self, sentence):

        # Do some validating
        if 'token_span' not in sentence:
            raise ValueError("`sentence['token_span']` must be TokenSpan-like")
        sentence = parc_reader.spans.Span(sentence, absolute=True)
        self.validate_sentence_span(sentence)

        # Add the sentence
        sentence_id = len(self.sentences)
        sentence['id'] = sentence_id
        self.sentences.append(sentence)

        # Add sentence-relative ids to the tokens for this sentence
        self.write_relative_token_ids_in_sentence(sentence_id)


    def validate_sentence_span(self, sentence):

        _, start, end = sentence['token_span'].get_single_range()

        # The first sentence should start at token zero.
        if len(self.sentences) == 0:
            if not start == 0:
                raise ValueError("First sentence should start with token 0.")

        # Ensure this sentence ends where the last one picked up.
        else:
            last_sentence = self.sentences[len(self.sentences) - 1]
            last_sentence_range = last_sentence['token_span'].get_single_range()
            _, last_start, last_end = last_sentence_range
            if start != last_end:
                raise ValueError(
                    "Non-adjacent sentences were added consecutively. "
                    "Sentences should be added in order, so that the first "
                    "token of a sentence being added should follow right after "
                    "the last token of the previously added sentence.  The "
                    "previously added sentence ended at token %d, and the "
                    "currently-added sentence starts at token %d"
                    % (last_end-1, start)
                )


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
        new_token_ranges = []

        for token_range in token_ranges:

            dummy_sentence_id, start, end = token_range
            if dummy_sentence_id is not None:
                ValueError('Cannot relativize token range: already relative.')

            successfully_relativized_range = False

            for sentence_id, sentence in enumerate(self.sentences):

                _, sent_start, sent_end = sentence['token_span'][0]

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


    def merge_tokens(
        self,
        other,
        copy_token_fields,
        copy_annotations,
        verbose=False
    ):

        # Copy over annotations
        for annotation in copy_annotations:
            self.annotations[annotation] = other.annotations[annotation]

        self_token_pointer = 0
        for other_token_pointer, other_token in enumerate(other.tokens):

            try:
                self_token = self.tokens[self_token_pointer]
            except IndexError:
                if other_token['text'] == '.':
                    continue
                raise

            self_text, other_text = self_token['text'], other_token['text']
            print self_text, other_text

            # Skip the stray apostraphe in doc 63.
            if self.doc_id == 63:
                if self_token['abs_id'] == 291:
                    continue
            
            force_same_token = False
            if self.doc_id == 2201:
                if self_token['abs_id'] == 890:
                    other_text = self_text
                    force_same_token = True

            # If they are the same token, merge the annotations
            if is_same_token(self_text, other_text) or force_same_token:
                self_token.update(t4k.select(other_token, copy_token_fields))

            # If the new token is a subset of the existing token, split
            # the existing token
            elif startswith(self_text, other_text):
                prefix, postfix = match_split(self_text, other_text)
                print (
                    '\t\tdoc #%d, token %d, splitting "%s" into "%s" and "%s"'
                    % (
                        self.doc_id, self_token['abs_id'], self_text,
                        prefix, postfix
                    )
                )
                self_token, remainder = self.split_token(self_token, other_text)
                self_token.update(t4k.select(other_token, copy_token_fields))

            elif self_text == other.tokens[other_token_pointer+1]['text']:
                continue

            else:
                raise ValueError(
                    '\t\tdoc #%d, token %d, expecting "%s" got "%s"'
                    % (self.doc_id,self_token['abs_id'],self_text,other_text)
                )

            self_token_pointer += 1


    def split_token(self, token, partial_text):

        abs_index = token['abs_id'] + 1

        prefix, postfix = match_split(token['text'], partial_text)

        token['text'] = partial_text
        remainder_token = dict(token, text=postfix)
        self.insert_token(abs_index, remainder_token)

        return token, remainder_token


    # TODO: alter this to use the new implementation of write_token_ids()
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


    def write_relative_token_ids_in_sentence(self, sentence_id):
        for token_id, token in enumerate(self.get_sentence_tokens(sentence_id)):
            token['id'] = token_id
            token['sentence_id'] = sentence_id


    def write_token_ids(self):
        for abs_id, token in enumerate(self.tokens):
            token['abs_id'] = abs_id
        for sentence_id in range(len(self.sentences)):
            self.write_relative_token_ids_in_sentence(sentence_id)



def match_split(text1, text2):
    text1_ = text1.replace("`", "'")
    text2_ = text2.replace("`", "'")

    ptr1, ptr2 = 0, 0
    while ptr1 < len(text1_) and ptr2 < len(text2_):
        if text1_[ptr1].lower() == text2_[ptr2].lower():
            ptr1 += 1
            ptr2 += 1
        elif text1_[ptr1] in "`'" and text2[ptr2] in "`'":
            ptr1 += 1
            ptr2 += 1
        elif text1_[ptr1] == 'E':
            ptr1 += 1
        else:
            raise ValueError(
                'could not match-split tokens "%s" and %s'
                % (text1, text2)
            )

    prefix, postfix = text1[:ptr1], text1[ptr1:]
    return prefix, postfix


def startswith(text1, text2):

    text1 = text1.replace("`", "'")
    text2 = text2.replace("`", "'")

    if text1.lower().startswith(text2.lower()):
        return True

    ptr1, ptr2 = 0, 0
    match = True
    while ptr1 < len(text1) and ptr2 < len(text2):
        if text1[ptr1].lower() == text2[ptr2].lower():
            ptr1 += 1
            ptr2 += 1
        elif text1[ptr1] in "`'" and text2[ptr2] in "`'":
            ptr1 += 1
            ptr2 += 1
        elif text1[ptr1] == 'E':
            ptr1 += 1
        else:
            match = False
            break

    return match


def is_same_token(text1, text2):
    text1 = text1.replace("`", "'")
    text2 = text2.replace("`", "'")
    if translation(text1).lower() == text2.lower():
        return True
    if (set(text1.lower()) - set(text2.lower())) == set('e'):
        return True
    return False


TRANSLATOR = {
    'S.p.EA.': 'S.p.A.',
    '7\/E16': '7\/16',
    u'\xd5TPA\xe5': 'TPA',
    '<Tourism': 'Tourism',
    'Bard\/EEMS': 'Bard\/EMS',
    '`S': "'S",
    "'T": "'T-",
    "H.\EF.": "H.F.",
    u"\xd5and\xe5": "and",
    u"\xd5illegal": "illegal",
    u'exports\xe5': 'exports',
    "16/": "16",
    u'\xd5Fifth\xe5': 'Fifth',
    "`n'": "'n'"
}

def translation(string):
    if string in TRANSLATOR:
        return TRANSLATOR[string]
    return string

