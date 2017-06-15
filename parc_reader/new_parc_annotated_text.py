from parc_reader.parc_sentence import ParcSentence
from bs4 import BeautifulSoup as Soup
from collections import defaultdict

ROLES = {'cue', 'content', 'source'}


def get_attributions(parc_xml, include_nested=True):

    # Our main concern is to build attributions, including their 
    # associations to tokens and sentences
    attributions = defaultdict(
        lambda: {'sentences':set(), 'source':[],'cue':[],'content':[]}
    )

    # Parse the xml.
    soup = Soup(parc_xml, 'html.parser')

    # Iterate through sentence / token tags, and find attribution tags
    sentence_tags = soup.find_all('sentence')
    for sentence_id, sentence_tag in enumerate(sentence_tags):
        word_tags = sentence_tag.find_all('word')
        for word_id, word_tag in enumerate(word_tags):

            attribution_tags = word_tag.find_all('attribution')
            for attribution_tag in attribution_tags:

                # Include nested attributions only if desired
                if not include_nested and 'Nested' in _id:
                    continue

                # Get / create an attribution object for this attribution
                attribution = attributions[attribution_tag['id']]

                # Note this token's role in the attribution, and note this
                # sentence's involvment in the attribution.
                role = attribution_tag.find('attributionrole')['rolevalue']
                attribution[role].append((sentence_id, word_id))
                attribution['sentences'].add(sentence_id)

    return attributions
