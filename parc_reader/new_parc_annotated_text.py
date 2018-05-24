from parc_reader.parc_sentence import ParcSentence
import parc_reader
from bs4 import BeautifulSoup as Soup
from collections import defaultdict
from brat_reader import BratAnnotatedText

ROLES = {'cue', 'content', 'source'}

def new_annotation():
    return {'sentences':set(), 'source':[],'cue':[],'content':[]}



def read_parc_file(parc_xml, doc_id=None, include_nested=False):
    """
    This reads in annotation information from parc xml files.  
    It includes the following annotations:

        (1) tokenizations,
        (2) sentence splitting,
        (3) part-of-speech tags,
        (4) constituent parse tree structure, and
        (5) attribution relations.

    Because it carries it's own alignment of annotations onto tokens, it
    can be combined with annotations whose opinion on tokenization differs
    slightly, as long as some effort to reconcile tokens is made. 
    """
    soup = Soup(parc_xml, 'html.parser')
    sentence_wrapper_tags = soup.find_all('sentence')
    annotated_doc = parc_reader.annotated_document.AnnotatedDocument(
        doc_id=doc_id)
    all_attributions = []
    #print 'doc_id', doc_id
    for sentence_id, sentence_wrapper_tag in enumerate(sentence_wrapper_tags):
        real_sentence_tag = parc_reader.utils.first_non_text_child(
            sentence_wrapper_tag)
        sentence, attributions = recursively_parse(
            real_sentence_tag, annotated_doc, include_nested=include_nested)
        all_attributions.extend(attributions)

    # Assemble attribution fragments and use sentence-relative addressing
    attributions = stitch_attributions(all_attributions, annotated_doc)
    annotated_doc.annotations['attributions'] = attributions

    # Make non-sentence constituents use sentence-relative addressing
    for sentence in annotated_doc.sentences:
        for child in sentence['constituent_children']:
            child.relativize(annotated_doc)

    return annotated_doc



def stitch_attributions(attribution_specs, annotated_doc):
    attributions = {}
    for attribution_spec in attribution_specs:
        attr_id = attribution_spec['id']
        if attr_id not in attributions:
            attribution = parc_reader.spans.Attribution(absolute=True)
            attributions[attr_id] = attribution
        else:
            attribution = attributions[attr_id]

        roles = attribution_spec['roles']
        for role in roles:
            attribution[role].add_token_ranges(attribution_spec['token_span'])

    for attribution in attributions.values():
        for role in attribution.ROLES:
            attribution[role].consolidate()
        attribution.relativize(annotated_doc)

    return attributions



def recursively_parse(tag, annotated_doc, depth=0, include_nested=True):

    # Make sure we're doing the right thing
    node_type = tag.name.lower()
    if node_type == 'attribution' or node_type == 'word':
        raise ValueError(
            'Expected non-token constituency tag.  Got <%s>.'
            % tag.name.lower())

    # We're building a constituency parse node from an xml tag.
    # Each constituent is modelled as a span that has direct references to its
    # children.  Then need to be modelled as absolute spans at first.
    node = parc_reader.spans.Constituency({
        'constituent_type': node_type
    }, absolute=True, **tag.attrs)

    # We'll capture attributions from children
    attributions = []

    # Parse the children
    for child_tag in parc_reader.utils.non_text_children(tag):

        # We shouldn't encounter attributions as direct children of internal
        # constituency nodes.
        if child_tag.name.lower() == 'attribution':
            print 'this node:', node
            print 'this tag:', tag
            raise ValueError(
                'Got <attribution> tag.  Expecting a constituency tag.')

        # Handle parsing child tokens
        elif child_tag.name.lower() == 'word':
            child_node = parse_token(child_tag, include_nested)
            child_node['sentence_id'] = len(annotated_doc.sentences)
            child_attributions = child_node['attributions']

            abs_id = annotated_doc.add_token(child_node)
            token_pointer = (None, abs_id, abs_id+1)
            for attribution in child_attributions:
                attribution['token_span'].add_token_range(token_pointer)
            node['token_span'].add_token_range(token_pointer)

            # As usual, we only want to provide a pointer to tokens, but for
            # consistency in traversing the constituency tree, the token should
            # appear in the node's constituent_children list.  We provide only
            # a stub to create the link
            node['constituent_children'].append(
                parc_reader.spans.Constituency({
                    'constituent_type': 'token',
                    'sentence_id': len(annotated_doc.sentences),
                    'token_span': [(None, abs_id, abs_id+1)]
                }, absolute=True)
            )

        # Handle parsing child internal constituency nodes
        else:
            child_node, child_attributions = recursively_parse(
                child_tag, annotated_doc, depth+1, include_nested)

            # Refuse children that are <none> tags
            if child_node['constituent_type'] == 'none':
                continue

            # Refuse children that themselves have no children, depste not
            # being tokens.
            if len(child_node['constituent_children']) == 0:
                continue

            node['token_span'].add_token_ranges(child_node['token_span'])
            node['constituent_children'].append(child_node)

        attributions.extend(child_attributions)

    node['token_span'].consolidate()
    if depth == 0:
        annotated_doc.add_sentence(node)

    return node, attributions


def parse_token(tag, include_nested=True):
    """
    Base case of the recursive parsing of parc xml.  Parsing of a token.
    Calls out to a subroutine to parse any attribution information on the token.
    """

    # Make sure we're doing the right thing
    tag_name = tag.name.lower()
    if tag_name != 'word':
        raise ValueError('Expecting a <word> tag, but got <%s>' % tag_name)

    # We're building a leaf node in the constituency parse; a *token*.
    node = {'is_token': True}
    node.update(tag.attrs)
    node['is_token'] = True

    # Correct an inconsistency in WSJ document 4 of PTB2
    if tag['gorn'].split(',')[0] == '1':
        if node['text'] == 'IBC/Donoghue':
            node['text'] = 'IBC'

    # Tokens don't have children in the constituency parse, but the attribution
    # annotations appear as children in the xml.
    node['attributions'] = []

    # Parse any attribution tags.  Ignore nested ones if desired.
    for attr_tag in parc_reader.utils.non_text_children(tag):
        attribution = parse_attribution(attr_tag)
        if not include_nested and 'Nested' in attribution['id']:
            continue
        node['attributions'].append(attribution)

    return node


def parse_attribution(tag):
    return parc_reader.spans.Span({
        'id': tag['id'],
        'roles': [role_tag['rolevalue'] for role_tag in tag('attributionrole')]
    }, absolute=True)



def get_attributions(parc_xml, include_nested=False):
    """
    This reads in annotation information from parc xml files.
    It only takes the attribution relations.  Because it has no intrinsic
    alignment, it must be combined with another resource that is known to have
    the same tokenization and sentence-splitting structure.  The CoreNLP
    annotations do, because the parc files were used to generate pre-tokenized
    raw text where tokenization is based on spaces and sentences are based on
    newlines, and the CoreNLP annotations were generated in respect of this.
    """

    # Our main concern is to build attributions, including their 
    # associations to tokens and sentences
    attributions = defaultdict(new_annotation)

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
    """
    Reads attributions from a BRAT annotation file.  This is a different format
    than the PARC format, but it holds pretty much the same information
    """
    #return parc_reader.BratAnnotation(annotation_text).attribution_specs

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

