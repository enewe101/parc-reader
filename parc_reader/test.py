from collections import defaultdict
from unittest import main, TestCase
from parc_reader.new_reader import ParcCorenlpReader, ROLES
import parc_reader
import t4k


class TestReadAllAnnotations(TestCase):

    def test_read_all_annotations(self):
        dataset = parc_reader.bnp_pronouns_reader.read_bnp_pronoun_dataset(
            skip=0,limit=20)
        print len(dataset)


class TestMergingPropbankVerbs(TestCase):

    def setUp(self):
        self.propbank_verbs_by_doc = (
            parc_reader.bnp_pronouns_reader.read_propbank_verbs())

    def get_test_docs(self, doc_id):
        parc_doc = parc_reader.parc_dataset.load_parc_doc(
            doc_id, include_nested=False)
        propbank_verbs = self.propbank_verbs_by_doc[doc_id]
        return parc_doc, propbank_verbs

    def test_several_docs_for_propbank_merging(self):
        for doc_id in [13, 17, 23, 29, 31, 37]:
            self.do_test_one_doc_for_propbank_merging(doc_id)


    MAX_DISTANCE_FOR_TOKEN_MATCH = 10
    def do_test_one_doc_for_propbank_merging(self, doc_id):

        parc_doc, propbank_verbs = self.get_test_docs(doc_id)
        parc_reader.bnp_pronouns_reader.merge_propbank_verbs(
            parc_doc, propbank_verbs)

        for verb_id, (sentence_id,token_id,lemma) in enumerate(propbank_verbs):
            matched_token = parc_doc.annotations['propbank_verbs'][verb_id]
            matched_lemma = matched_token['lemma']
            matched_location = parc_doc.absolutize(matched_token['token_span'])
            matched_abs_id = matched_location[0][1]
            expected_location = parc_doc.absolutize(
                [(sentence_id, token_id, token_id + 1)])
            expected_location_abs_id = expected_location[0][1]
            distance = matched_abs_id - expected_location_abs_id
            self.assertEqual(lemma, matched_lemma)
            self.assertTrue(abs(distance) < self.MAX_DISTANCE_FOR_TOKEN_MATCH)








class TestTokenSpan(TestCase):

    def test_bad_span(self):
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan([(0, 0, 0)])
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan([(0, 1, 0)])
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan(single_range=(0, 0, 0))
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan(single_range=(0, 1, 0))
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan([(0, 1, 0)], absolute=True)
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan([(None, 1, 0)])
        with self.assertRaises(ValueError):
            parc_reader.spans.TokenSpan(single_range=(0,1))


    def test_consolidation(self):

        # Consolidation when one span is adjacent to another
        t1 = parc_reader.spans.TokenSpan([(0,0,1), (0,1,2)])
        t2 = parc_reader.spans.TokenSpan([(0,0,2)])
        self.assertEqual(t1, t2)

        # Consolidating when one span subsumes another
        t1 = parc_reader.spans.TokenSpan([(0,0,2), (0,1,3)])
        t2 = parc_reader.spans.TokenSpan([(0,0,3)])
        self.assertEqual(t1, t2)

        # Consolidation of unordered ranges works, and equality is maintained.
        t1 = parc_reader.spans.TokenSpan([(0,1,2), (0,0,1)])
        t2 = parc_reader.spans.TokenSpan([(0,0,2)])
        self.assertEqual(t1, t2)

        # Equality is not affected by order.
        t1 = parc_reader.spans.TokenSpan([(0,2,3), (0,0,1)])
        t2 = parc_reader.spans.TokenSpan([(0,0,1), (0,2,3)])
        self.assertEqual(t1, t2)


    def test_good_span(self):
        parc_reader.spans.TokenSpan(single_range=(0,0,1))
        parc_reader.spans.TokenSpan(single_range=(0,1), absolute=True)
        parc_reader.spans.TokenSpan(single_range=(None,0,1), absolute=True)


    def test_len(self):
        empty_span = parc_reader.spans.TokenSpan()
        self.assertEqual(len(empty_span), 0)
        span_with_overlaps = parc_reader.spans.TokenSpan(
            [(0,3), (1,4)], absolute=True)
        self.assertEqual(len(span_with_overlaps), 4)




class TestReadParcFile(TestCase):

    # TODO: test token splitting

    def setUp(self):
        self.doc = self.get_test_doc()


    def get_test_doc(self, include_nested=True):
        first_interesting_article = 3
        path = parc_reader.parc_dataset.get_parc_path(first_interesting_article)
        xml = open(path).read()
        return parc_reader.new_parc_annotated_text.read_parc_file(
            xml, include_nested=include_nested)


    def test_num_attributions(self):
        """Ensure the correct number of attributions is found for the file."""
        num_attributions = len(self.doc.annotations['attributions'])
        expected_num_attributions = 13
        condition = num_attributions == expected_num_attributions,
        self.assertTrue(condition, 'incorrect number of attributions found')


    def test_attribution_spans_have_correct_tokens(self):
        """
        Ensure that a given attribution has the correct tokens in its
        source, cue, and content spans.
        """
        annotation_id = 'wsj_0003_Attribution_relation_level.xml_set_1'
        annotation = self.doc.annotations['attributions'][annotation_id]

        # Check that the source span and source text is correct
        expected_source_token_span = [(0,33,34)]
        self.assertEqual(annotation['source'], expected_source_token_span)

        expected_source_text = "researchers"
        found_source_text = self.doc.get_tokens(annotation['source']).text()
        self.assertEqual(found_source_text, expected_source_text)

        # Check that the cue span and cue text is correct
        expected_cue_token_span = [(0,34,35)]
        self.assertEqual(annotation['cue'], expected_cue_token_span)

        found_cue_text = self.doc.get_tokens(annotation['cue']).text()
        expected_cue_text = 'reported'
        self.assertEqual(found_cue_text, expected_cue_text)

        # Check that the content span and content text is correct
        expected_content_token_span = [(0,0,32)]
        self.assertEqual(annotation['content'], expected_content_token_span)

        found_content_text = self.doc.get_tokens(annotation['content']).text()
        expected_content_text = (
            "A form of asbestos once used to make Kent cigarette filters has "
            "caused a high percentage of cancer deaths among a group of workers"
            " exposed to it more than 30 years ago"
        )
        self.assertEqual(found_content_text, expected_content_text)


    def test_token_reference_to_attributions(self):

        found_token_references = defaultdict(
            lambda: {'source':set(), 'cue':set(), 'content':set()}
        )

        # First, iterate through all the tokens, and accumulate all those that
        # refer to attributions, according to which attribution / role they
        # reference.
        for token_id, token in enumerate(self.doc.tokens):
            for attribution in token['attributions']:
                for role in attribution['roles']:
                    attr_id = attribution['id']
                    found_token_references[attr_id][role].add(token_id)

        # Check that we got the complete set of attributions by accumulating
        # them from token references.
        self.assertEqual(
            found_token_references.keys(),
            self.doc.annotations['attributions'].keys()
        )

        # Now, go through each attribution, and check that we got all the same
        # tokens for each role in each attribution by accumulating them from
        # token references.
        attributions = self.doc.annotations['attributions']
        for attribution_id, attribution in attributions.items():
            for role in attribution.ROLES:
                token_ids = {
                    t['abs_id'] for t in self.doc.get_tokens(attribution[role])
                }
                self.assertEqual(
                    found_token_references[attribution_id][role],
                    token_ids, 
                )

    def test_exclude_nested(self):
        expected_num_nested = 3
        num_nested = len([
            key for key in 
            self.doc.annotations['attributions'].keys()
            if 'Nested' in key
        ])
        self.assertEqual(num_nested, expected_num_nested)

        doc_without_nested = self.get_test_doc(include_nested=False)
        excluded = (
            set(self.doc.annotations['attributions'].keys())
            - set(doc_without_nested.annotations['attributions'].keys())
        )
        self.assertEqual(len(excluded), expected_num_nested)
        self.assertTrue(all('Nested' in attr_id for attr_id in excluded))


    def test_tokens_pos_tags(self):
        found_pos = [t['pos'] for t in self.doc.get_sentence_tokens(1)]
        expected_pos = [
            'DT', 'NN', 'NN', 'COLON', 'NN', 'COLON', 'VBZ', 'RB', 'JJ', 'IN', 
            'PRP', 'VBZ', 'DT', 'NNS', 'COLON', 'IN', 'RB', 'JJ', 'NNS', 'TO', 
            'PRP', 'VBG', 'NNS', 'WDT', 'VBP', 'RP', 'NNS', 'JJ', 'COLON', 
            'NNS', 'VBD', 'PKT'
        ]
        condition = found_pos == expected_pos
        self.assertEqual(found_pos, expected_pos)


    def test_constituency_parse_tree_structure(self):
        """
        Ensure that the constituent tree is correct.
        """
        # Check that a DFS yields the correct sequence of constituents
        constituent = self.doc.sentences[0]
        found_dfs_sequence = [
            (depth, node['constituent_type']) 
            for depth, node in 
            parc_reader.spans.get_dfs_constituents(constituent)
        ]
        expected_dfs_sequence = [
            (0, u's'), (1, u's-tpc-1'), (2, u'np-sbj'), (3, u'np'), (4, u'np'),
            (5, 'token'), (5, 'token'), (4, u'pp'), (5, 'token'), (5, u'np'),
            (6, 'token'), (3, u'rrc'), (4, u'advp-tmp'), (5, 'token'),
            (4, u'vp'), (5, 'token'), (5, u's-clr'), (6, u'vp'), (7, 'token'),
            (7, u'vp'), (8, 'token'), (8, u'np'), (9, 'token'), (9, 'token'),
            (9, 'token'), (2, u'vp'), (3, 'token'), (3, u'vp'), (4, 'token'),
            (4, u'np'), (5, u'np'), (6, 'token'), (6, 'token'), (6, 'token'),
            (5, u'pp'), (6, 'token'), (6, u'np'), (7, 'token'), (7, 'token'),
            (5, u'pp-loc'), (6, 'token'), (6, u'np'), (7, u'np'), (8, 'token'),
            (8, 'token'), (7, u'pp'), (8, 'token'), (8, u'np'), (9, u'np'),
            (10, 'token'), (9, u'rrc'), (10, u'vp'), (11, 'token'),
            (11, u'pp-clr'), (12, 'token'), (12, u'np'), (13, 'token'),
            (11, u'advp-tmp'), (12, u'np'), (13, u'qp'), (14, 'token'),
            (14, 'token'), (14, 'token'), (13, 'token'), (12, 'token'),
            (1, 'token'), (1, u'np-sbj'), (2, 'token'), (1, u'vp'),
            (2, 'token'), (1, 'token')
        ]
        self.assertEqual(found_dfs_sequence, expected_dfs_sequence)


    def test_constituency_token_spans(self):
        """
        Test that sentence constituents are still absolutely addressed, and 
        that all other constituents have been converted to sentence-relative 
        addressing.
        """
        
        # Choose anything except the first sentence.  We need to make sure that 
        # the constituents' token_spans are addressed relative to the start of
        # the sentence
        TEST_SENTENCE_INDEX = 1

        # First check that the sentence constituent has correct absolute token
        # span
        found_token_span = self.doc.sentences[TEST_SENTENCE_INDEX]['token_span']
        sent_abs_start, sent_abs_end = 36, 68
        expected_token_span = [(None, sent_abs_start, sent_abs_end)]
        self.assertEqual(found_token_span, expected_token_span)

        
        # Now check that all other constituents have correct sentence-relative
        # token spans
        nodes_in_dfs_order = parc_reader.spans.get_dfs_constituents(
            self.doc.sentences[TEST_SENTENCE_INDEX])

        max_end = t4k.Max()

        past_first_token = False
        for depth, node in nodes_in_dfs_order:

            if depth == 0:
                continue

            self.assertEqual(len(node['token_span']), 1)
            sentence_id, start, end = node['token_span'][0]
            max_end.add(end)

            last_end = None
            #print depth, node['constituent_type']
            #print 'start, end\t', start, end, last_end

            # All token_spans should be addressed to the test sentence's ID
            self.assertEqual(sentence_id, TEST_SENTENCE_INDEX)

            # The first constituents and tokens should have an index of zero
            if not past_first_token:
                self.assertEqual(start, 0)

            for child in parc_reader.spans.get_constituency_children(node):
                self.assertEqual(len(child['token_span']), 1)
                token_span = child['token_span'][0]
                child_sentence_id, child_start, child_end = token_span
                self.assertEqual(child_sentence_id, sentence_id)

                # One child should pick up where the preceeding child left off
                # (Except for the first child, which has no preceeding child)
                if last_end is not None:
                    self.assertEqual(child_start, last_end)

                self.assertTrue(child_end <= end)
                last_end = child_end
                #print ' '.join(t4k.strings([],
                #    '\tchild_start, child_end, last_end\t',
                #    child_start, child_end, last_end
                #))

            if last_end is not None:
                #print 'did final child line up?\t', last_end, end
                self.assertEqual(last_end, end)

            if node['constituent_type'] == 'token':
                past_first_token = True

        self.assertEqual(max_end.max_key(), sent_abs_end - sent_abs_start)
        







def get_test_texts(article_num, include_parc=True):
    texts = []
    texts.append(open('data/example-corenlp-%d.xml' % article_num).read())
    if include_parc:
        texts.append(open('data/example-parc-%d.xml' % article_num).read())
    texts.append(open('data/example-raw-%d.txt' % article_num).read())
    return texts


def get_test_article(article_num, include_parc=True):
    return ParcCorenlpReader(*get_test_texts(article_num, include_parc))


class TestReader(TestCase):

    def test_add_attributions_incremental(self):
        # Open an article, but exclude the parc file
        article_with_attributions = get_test_article(1)
        article_no_attributions = get_test_article(1, include_parc=False)

        # One copy of the file has no attributions.
        self.assertEqual(len(article_with_attributions.attributions), 25)
        self.assertEqual(len(article_no_attributions.attributions), 0)

        # We'll add an atttribution to the article that has none.  Base it 
        # on one of the actual attributions
        attr_id = 'wsj_0018_PDTB_annotation_level.xml_set_5'
        attr = article_with_attributions.attributions[attr_id]

        article_no_attributions.add_attribution(attribution_id=attr_id)

        # Add tokens to the recently added attribution
        article_no_attributions.add_to_attribution(
            attr_id, 'source', attr['source'])

        # Add tokens, this time using sentence_id, token_id tuples
        article_no_attributions.add_to_attribution(
            attr_id, 'cue', [(t['sentence_id'], t['id']) for t in attr['cue']])

        # Add the tokens for the content
        article_no_attributions.add_to_attribution(
            attr_id, 'content', attr['content'])
        
        # Check that the attribution now exists and has the correct structure
        added_attr = article_no_attributions.attributions[attr_id]

        # Check correctness of source
        expected_source = [(9, 0), (9, 1)]
        self.assertEqual(
            expected_source, 
            [(t['sentence_id'], t['id']) for t in added_attr['source']]
        )

        # Check correctness of cue
        expected_cue = [(9, 2), (9, 3)]
        self.assertEqual(
            expected_cue, 
            [(t['sentence_id'], t['id']) for t in added_attr['cue']]
        )

        # Check correctness of content
        expected_content = [
            (9, 4), (9, 5), (9, 6), (9, 7), (9, 8), (9, 9), (9, 10), (9, 11), 
            (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (9, 18)
        ]
        self.assertEqual(
            expected_content, 
            [(t['sentence_id'], t['id']) for t in added_attr['content']]
        )

        # Check that all of the tokens involved in the attribution got the 
        # proper role and link to the attribution, and that no others did
        token_roles = {
            'source': set(expected_source),
            'cue': set(expected_cue),
            'content': set(expected_content)
        }
        for sentence in article_no_attributions.sentences:

            # Check that all of the tokens involved in the attribution got the 
            # proper role and link to the attribution, and that no others did
            for token in sentence['tokens']:
                sentence_id, token_id = token['sentence_id'], token['id']
                for role in ROLES:

                    # If this token has a role in the attribution, make sure
                    # we see it on the token
                    if (sentence_id, token_id) in token_roles[role]:
                        self.assertEqual(token['attributions'].keys(),[attr_id])
                        self.assertTrue(role in token['attributions'][attr_id])

                        # also check that the sentence records its association
                        # to this attribution
                        self.assertTrue(attr_id in sentence['attributions'])
                        self.assertEqual(len(sentence['attributions']), 1)

                    # If the token doesn't belong to this role in the
                    # attribution then we shouldn't see that role on the token.
                    else:

                        # We should see no entries for any attributions
                        if attr_id not in token['attributions']:
                            self.assertEqual(len(token['attributions']), 0)

                        # Or if this token might have a different role, but
                        # on the same attribution.  Still, it should not show
                        # this role.
                        else:
                            self.assertEqual(
                                token['attributions'].keys(),[attr_id])
                            self.assertTrue(
                                role not in token['attributions'][attr_id])


    def test_add_attributions(self):

        # Open an article, but exclude the parc file
        article_with_attributions = get_test_article(1)
        article_no_attributions = get_test_article(1, include_parc=False)

        # One copy of the file has no attributions.
        self.assertEqual(len(article_with_attributions.attributions), 25)
        self.assertEqual(len(article_no_attributions.attributions), 0)

        # We'll add an atttribution to the article that has none.  Base it 
        # on one of the actual attributions
        attr_id = 'wsj_0018_PDTB_annotation_level.xml_set_5'
        attr = article_with_attributions.attributions[attr_id]

        article_no_attributions.add_attribution(
            attr['cue'], attr['content'], attr['source'], attr_id
        )
        
        # Check that the attribution now exists and has the correct structure
        added_attr = article_no_attributions.attributions[attr_id]

        # Check correctness of source
        expected_source = [(9, 0), (9, 1)]
        self.assertEqual(
            expected_source, 
            [(t['sentence_id'], t['id']) for t in added_attr['source']]
        )

        # Check correctness of cue
        expected_cue = [(9, 2), (9, 3)]
        self.assertEqual(
            expected_cue, 
            [(t['sentence_id'], t['id']) for t in added_attr['cue']]
        )

        # Check correctness of content
        expected_content = [
            (9, 4), (9, 5), (9, 6), (9, 7), (9, 8), (9, 9), (9, 10), (9, 11), 
            (9, 12), (9, 13), (9, 14), (9, 15), (9, 16), (9, 17), (9, 18)
        ]
        self.assertEqual(
            expected_content, 
            [(t['sentence_id'], t['id']) for t in added_attr['content']]
        )

        # Check that all of the tokens involved in the attribution got the 
        # proper role and link to the attribution, and that no others did
        token_roles = {
            'source': set(expected_source),
            'cue': set(expected_cue),
            'content': set(expected_content)
        }
        for sentence in article_no_attributions.sentences:

            # Check that all of the tokens involved in the attribution got the 
            # proper role and link to the attribution, and that no others did
            for token in sentence['tokens']:
                sentence_id, token_id = token['sentence_id'], token['id']
                for role in ROLES:

                    # If this token has a role in the attribution, make sure
                    # we see it on the token
                    if (sentence_id, token_id) in token_roles[role]:
                        self.assertEqual(token['attributions'].keys(),[attr_id])
                        self.assertTrue(role in token['attributions'][attr_id])

                        # also check that the sentence records its association
                        # to this attribution
                        self.assertTrue(attr_id in sentence['attributions'])
                        self.assertEqual(len(sentence['attributions']), 1)

                    # If the token doesn't belong to this role in the
                    # attribution then we shouldn't see that role on the token.
                    else:

                        # We should see no entries for any attributions
                        if attr_id not in token['attributions']:
                            self.assertEqual(len(token['attributions']), 0)

                        # Or if this token might have a different role, but
                        # on the same attribution.  Still, it should not show
                        # this role.
                        else:
                            self.assertEqual(
                                token['attributions'].keys(),[attr_id])
                            self.assertTrue(
                                role not in token['attributions'][attr_id])



    def test_reader(self):

        # Get a first article to test.
        article1 = get_test_article(1)
        self.assertEqual(len(article1.attributions), 25)

        # Get a second article to test.
        article2 = get_test_article(2)

        # First, check that the correct number of attributions were identified
        # (should only be one)
        self.assertEqual(len(article2.attributions), 1)

        # Now check the structure of that attribution.  This attribution is
        # somewhat special because the source and cue actually coincide,
        # meaning that those tokens have two roles within the attribution.
        attr = article2.attributions['wsj_1655_PDTB_annotation_level.xml_set_0']

        # Check that the correct tokens for the source were found
        expected_source = [(15, 4), (15, 5)]
        self.assertEqual(
            expected_source,
            [(t['sentence_id'], t['id']) for t in attr['source']]
        )

        # Check that the correct tokens for the cue were found
        expected_cue = [(15, 4), (15, 5)]
        self.assertEqual(
            expected_cue,
            [(t['sentence_id'], t['id']) for t in attr['cue']]
        )

        # Check that the correct tokens for the content were found
        sentence_ids = range(15,27)
        token_ranges = [(15,50), (5,), (16,), (4,), (28,), (5,), (5,), 
            (30,), (11,), (10,), (20,), (7,) ]
        expected_content = [
            (i, k) for i,j in zip(sentence_ids, token_ranges)
            for k in range(*j)
        ]
        self.assertEqual(
            expected_content,
            [(t['sentence_id'], t['id']) for t in attr['content']]
        )


    def test_writing_parc_xml(self):
        """
        Test that a write-read cycle preserves the attribution structure
        """
        self.do_read_write_test(1)
        self.do_read_write_test(2)


    def do_read_write_test(self, article_num):

        # First, open an article, and immediately serialize it to disc using
        # the article.get_parc_xml() function
        article = get_test_article(article_num)
        open('data/test-parc-output-%d.xml' % article_num, 'w').write(
            article.get_parc_xml())

        # Now read the serialized version of the xml (along with the original
        # corenlp and raw files).  It should give the exact same datastructure.
        reread_article = ParcCorenlpReader(
            open('data/example-corenlp-%d.xml' % article_num).read(),
            open('data/test-parc-output-%d.xml' % article_num).read(),
            open('data/example-raw-%d.txt' % article_num).read()
        )

        # First test that they have the same number of attributions
        self.assertEqual(
            len(reread_article.attributions), len(article.attributions))

        # Then test that each attribution contains the same tokens in the same
        # roles
        for attr_id, attr in article.attributions.items():
            reread_attr = reread_article.attributions[attr_id]
            for role in ROLES:
                tokens = [(t['sentence_id'], t['id']) for t in attr[role]]
                reread_tokens = [
                    (t['sentence_id'], t['id']) 
                    for t in reread_attr[role]
                ]
                self.assertEqual(reread_tokens, tokens)

        # Finally test that attribution associations written onto the tokens
        # and sentences themselves match too.
        for sent1, sent2 in zip(article.sentences, reread_article.sentences):
            self.assertEqual(sent1['attributions'], sent2['attributions'])
            for token1, token2 in zip(sent1['tokens'], sent2['tokens']):
                self.assertEqual(token1['attributions'], token2['attributions'])

if __name__ == '__main__':
    main()
