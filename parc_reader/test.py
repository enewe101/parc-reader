from unittest import main, TestCase
from parc_reader.new_reader import ParcCorenlpReader, ROLES

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
