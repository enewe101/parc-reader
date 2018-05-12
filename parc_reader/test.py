from unittest import main, TestCase
from parc_reader.new_reader import ParcCorenlpReader, ROLES
import parc_reader


class TestReadAllAnnotations(TestCase):

    def test_read_all_annotations(self):
        dataset = parc_reader.bnp_pronouns_reader.read_bnp_pronoun_dataset(
            skip=0,limit=20)
        print len(dataset)


class TestReadParcFile(TestCase):

    def test_read_parc_file(self):
        first_interesting_article = 3
        path = parc_reader.parc_dataset.get_parc_path(first_interesting_article)
        doc = parc_reader.new_parc_annotated_text.read_parc_file(
            open(path).read())

        annotation_id = 'wsj_0003_Attribution_relation_level.xml_set_1'
        annotation = doc.annotations['attributions'][annotation_id]

        condition = annotation['content'] == [(0,0,32)]
        self.assertTrue(condition, 'incorrect attribution content')

        found_content_text = doc.get_tokens(annotation['content']).text()
        expected_content_text = (
            "A form of asbestos once used to make Kent cigarette filters has "
            "caused a high percentage of cancer deaths among a group of workers "
            "exposed to it more than 30 years ago"
        )

        condition = found_content_text == expected_content_text
        self.assertTrue(condition, 'incorrect attribution content text')

        num_attributions = len(doc.annotations['attributions'])
        expected_num_attributions = 13
        condition = num_attributions == expected_num_attributions,
        self.assertTrue(condition, 'incorrect number of attributions found')

        constituent = doc.sentences[0]
        found_constituent_path = [constituent['constituent_type']]
        while len(constituent['constituent_children']) > 0:
            constituent = constituent['constituent_children'][0]
            found_constituent_path.append(constituent['constituent_type'])
        expected_constituent_path = ['s', 's-tpc-1', 'np-sbj', 'np', 'np', 'token']

        condition = (found_constituent_path==expected_constituent_path)
        self.assertTrue(condition, 'incorrect constituency tree')

        # Get the first constituent that has a token as its first direct child
        constituent = doc.sentences[0]
        first_child = constituent['constituent_children'][0]
        while first_child['constituent_type'] != 'token':
            constituent = first_child
            first_child = constituent['constituent_children'][0]
        found_token_span = constituent['token_span']

        expected_token_span = [(0,0,2)]
        condition = found_token_span == expected_token_span
        self.assertTrue(condition, 'incorrect token span')

        # Check that tokens have attribution information 
        for token in  doc.get_tokens(constituent['token_span']):
            attribution = token['attributions'][0]
            expected_attr_id = 'wsj_0003_Attribution_relation_level.xml_set_1'
            condition = attribution['id'] == expected_attr_id
            self.assertTrue(condition, 'incorrect attribution on token')
            condition = attribution['roles'][0] == 'content'
            self.assertTrue(condition, 'incorrect attribution role on token')
            condition = len(token['attributions']) == 1
            self.assertTrue(
                condition, 'incorrect number of attributions on token')
            condition = len(attribution['roles']) == 1
            self.assertTrue(
                condition, 'incorrect number of attributions on token')

        found_token_span = doc.sentences[0]['token_span']
        expected_token_span = [(None,0,36)]
        condition = found_token_span == expected_token_span
        self.assertTrue(condition, 'incorrect token span')

        attribution_id = 'wsj_0003_PDTB_annotation_level.xml_set_0'
        attribution = doc.annotations['attributions'][attribution_id]
        expected_spans = {
            'content': [(1, 0, 29)],
            'source': [(1, 29, 30)],
            'cue': [(1, 30, 31)]
        }
        for role in attribution.ROLES:
            condition = attribution[role] == expected_spans[role]
            self.assertTrue(
                condition, 'incorrect span for attribution[%s]' % role)

        found_pos = [t['pos'] for t in doc.get_sentence_tokens(1)]
        expected_pos = [
            'DT', 'NN', 'NN', 'COLON', 'NN', 'COLON', 'VBZ', 'RB', 'JJ', 'IN', 
            'PRP', 'VBZ', 'DT', 'NNS', 'COLON', 'IN', 'RB', 'JJ', 'NNS', 'TO', 
            'PRP', 'VBG', 'NNS', 'WDT', 'VBP', 'RP', 'NNS', 'JJ', 'COLON', 'NNS', 
            'VBD', 'PKT'
        ]
        condition = found_pos == expected_pos
        self.assertTrue(condition, 'incorrect parts of speech in sentence 1')

        return doc




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
