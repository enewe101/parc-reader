from parc_reader.parc_sentence import ParcSentence
from bs4 import BeautifulSoup as Soup
from collections import defaultdict
from brat_reader import BratAnnotatedText

ROLES = {'cue', 'content', 'source'}

def get_attributions(parc_xml, include_nested=False):

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
                if not include_nested and 'Nested' in attribution_tag['id']:
                    continue

                # Get / create an attribution object for this attribution
                attribution = attributions[attribution_tag['id']]

                # Note this token's role in the attribution, and note this
                # sentence's involvment in the attribution.
                role_tags = attribution_tag.find_all('attributionrole')
                roles = [role_tag['rolevalue'] for role_tag in role_tags]
                for role in roles:
                    attribution[role].append((sentence_id, word_id))
                    attribution['sentences'].add(sentence_id)

    return attributions


def get_attributions_from_brat(annotation_text):
    annotated_text = BratAnnotatedText(annotation_text)
    attributions = annotated_text.get_event_specs()

    # Every annotation consists of source, cue, and content spans.  But brat
    # also returns a span associated to the annotation itself, which we don't
    # need or want.  Filter that out of the annotations.
    return {
        attr_id: {
            span_type: span_range_spec
            for span_type, span_range_spec in attr_spec.iteritems()
            if span_type != 'attribution'
        }
        for attr_id, attr_spec in attributions.iteritems()
    }


# NOTE: Most of the logic previously in get_attributions_from_brat was moved
# into brat_reader.
#
#def get_attributions_from_brat(annotation_text):
#    """
#    Reads attributions from a BRAT annotation file.  This is a different format
#    than the PARC format, but it holds pretty much the same information
#    """
#
#    # Our main concern is to build attributions, including their 
#    # associations to tokens and sentences
#    attributions = defaultdict(
#        lambda: {'sentences':set(), 'source':[],'cue':[],'content':[]}
#    )
#
#    attribution_specs = {}
#    span_specs = {}
#    for line in annotation_text.split('\n'):
#
#        # Skip blank lines
#        if line == '': continue
#
#        # Every entry has a label, followed by a specification
#        label, spec = line.split('\t', 1)
#
#        # Labels starting with 'E' represent attributions, and they collect
#        # multiple spans together
#        if label.startswith('E'):
#
#            # The attribution spec has several role:label words separated by 
#            # spaces.  The "Source", "Cue", and "Content" roles are of interest
#            # but the "Attribution" role is redundant so we filter it out.
#            attribution = dict([
#                s.split(':') for s in spec.split()
#                if 'Attribution' not in s.split(':')[0]
#            ])
#            attribution_specs[label] = attribution
#
#        # Labels starting with 'T' represent spans
#        elif label.startswith('T'):
#
#            # Skip "Discuss" and "Discard" tags.
#            if spec.startswith('Disc'):
#                continue
#
#            # The span's spec consists of a role and range spec separated by a
#            # tab from a listing of the tokens under that range.  We don't want
#            # the token literals, just the role and range spec.
#            role_and_range_specs = spec.split('\t')[0]
#            role, range_specs = role_and_range_specs.split(' ', 1)
#
#            # The ranges are like `start end:start end:...`
#            # Separate individual ranges, parse out the start and endpoint for 
#            # each (converting them to ints)
#            ranges = [
#                tuple([int(i) for i in r.split(' ')]) 
#                for r in range_specs.split(';')
#            ]
#            span_specs[label] = ranges
#
#    # Within attribution specs, replace the span identifier with the range spec
#    # for the span.
#    finalized_attribution_specs = {
#        label: {key.lower(): span_specs[attr_spec[key]] for key in attr_spec}
#        for label, attr_spec in attribution_specs.iteritems()
#    }
#
#    return finalized_attribution_specs

