from xml.dom import minidom
from corenlp_xml_reader import Token


# This provisional dom is used as an element factory
DOM = minidom.Document()

def element(tag_name, attributes={}):
    elm = DOM.createElement(tag_name)
    bind_attributes(elm, attributes)
    return elm

def bind_attributes(element, attributes):
    for attribute in attributes:
        element.setAttribute(attribute, attributes[attribute])
    return element

def div(attributes={}):
    return element('div', attributes)

def span(attributes={}):
    return element('span', attributes)

def text(text_content):
    return DOM.createTextNode(text_content)



class AttributionHtmlSerializer(object):

    @classmethod
    def serialize_attributions(cls, attributions, resolve_pronouns=False):
        '''
        This accepts an iterable of Attribution objects, and produces
        an HTML page that visualizes them.
        '''
        # Make a dom and basic top-level page structure
        dom, body = cls.prepare_dom()
        for attribution in attributions:
            attribution_element = cls.get_attribution_element(
                attribution, resolve_pronouns)
            body.appendChild(attribution_element)

        return dom.toprettyxml(indent='  ')


    @classmethod
    def get_attribution_html(
        cls, attribution, resolve_pronouns=False,
        indent='', newl=' '
    ):
        attribution_element = cls.get_attribution_element(
            attribution, resolve_pronouns)
        return attribution_element.toprettyxml(indent=indent, newl=newl)



    @classmethod
    def get_attribution_element(cls, attribution, resolve_pronouns=False):

        # Get the source and cue head so they can be specially highlighted
        cue_head = cls.get_cue_head(attribution)
        source_head = cls.get_source_head(attribution)

        # Make an element to contain the markup for this attribution
        attribution_element = div({'class':'attribution'})

        # Get the sentences involved in the attribution, and get all their
        # tokens.
        sentences = cls.get_sentences(attribution)
        tokens = []
        for sentence in sentences:
            tokens += sentence['tokens']

        # Make html representation for each token, adding it to the attribution
        # element
        for token in tokens:

            roles = cls.get_token_roles(token, attribution)

            # Here we can optionally detect and resolve pronouns
            if resolve_pronouns and role == 'source':
                if is_substitutable_pronoun(token):
                    resolved_element = cls.make_resolved_element(
                        token, roles, cue_head, source_head)
                    attribution_element.appendChild(resolved_element)

            # But usually we just make the element for each token
            else:
                token_element = cls.make_token_element(
                    token, roles, cue_head, source_head)
                attribution_element.appendChild(token_element)

        return attribution_element


    @classmethod
    def prepare_dom(cls, additional_styling={}):

        # Make a document, and put the basic elements in it
        dom = minidom.Document()
        html = dom.appendChild(dom.createElement('html'))
        html.appendChild(
            cls.get_head_element(additional_styling=additional_styling))
        body = html.appendChild(dom.createElement('body'))

        return dom, body


    @classmethod
    def make_token_group_element(
        cls,
        token_group,
        resolve_pronouns,
        cue_head = None,
        source_head = None
    ):

        role, tokens = token_group
        group_element = span({'class':'role-%s' % role})

        for token in tokens:

            # Here we can optionally detect and resolve pronouns
            if resolve_pronouns and role == 'source':
                #if token['pos'] == 'PRP' or token['pos'] == 'PRP$':
                if is_substitutable_pronoun(token):
                    resolved_element = cls.make_resolved_element(
                        token, cue_head, source_head)
                    group_element.appendChild(resolved_element)
                    continue

            # But usually we just make the element for each token
            token_element = cls.make_token_element(
                token, cue_head, source_head)
            group_element.appendChild(token_element)

        return group_element


    @staticmethod
    def make_token_element(token, roles, cue_head=None, source_head=None):

        # check if element is the cue head or source head, and adjust 
        # token element's class accordingly
        _class = 'token'
        if len(roles) > 0:
            _class += ' ' + ' '.join(['role-%s' % role for role in roles])
        attrs = {'class':_class}
        if token is cue_head:
            attrs['class'] += ' cue-head'
        elif token is source_head:
            attrs['class'] += ' source-head'

        token_element = span(attrs)
        token_element.appendChild(text(token['word']))
        pos_element = token_element.appendChild(span({'class':'pos'}))
        inner_pos_element = pos_element.appendChild(
            span({'class':'pos-inner'}))
        inner_pos_element.appendChild(text(token['pos']))

        return token_element


    @classmethod
    def make_resolved_element(
        cls, token, roles, cue_head=None, source_head=None
    ):

        # Get the representative mention for the token, if any
        resolved_tokens = cls.substitute_pronoun_token(token)

        # If a representative element was found, make the html representing
        # it, leaving a stylable div wrapping the replacement text so
        # it can be visualized
        if resolved_tokens is not None:
            resolved_element = span({'class':'pronoun'})
            for resolved_token in resolved_tokens:
                token_element = cls.make_token_element(
                    resolved_token, roles, cue_head, source_head)
                resolved_element.appendChild(token_element)

        # Otherwise, just get the element for the original token
        else:
            resolved_element = cls.make_token_element(
                token, roles, cue_head, source_head)

        # Return the element, whether reprsenting replacement or original
        return resolved_element
    

    @staticmethod
    def substitute_pronoun_token(token):

        # Check if we have a representative mention that can be used
        # to substitute the pronoun.  If not, fail.
        if len(token['mentions']) == 0:
            return None

        # Get the tokens corresponding to the representative mention
        # for the coreference chain this pronoun is from.
        ref = token['mentions'][0]['reference']
        representative = ref['representative']

        # Check whether the representative is in the same sentence, in 
        # which case, don't replace
        representative = ref['representative']
        if representative['sentence_id'] == token['sentence_id']:
            return None

        # If this is the first position, then capitalize the first letter
        tokens = representative['tokens']
        if token['id'] == 0:
            capitalized = Token(tokens[0])
            capitalized['word'] = capitalized['word'].capitalize()
            tokens = [capitalized] + tokens[1:]

        return tokens


    @classmethod
    def group_tokens(cls, attribution):

        # Get the sentences involved in the attribution
        sentences = cls.get_sentences(attribution)

        # Get all the tokens, and group them into contiguous groups having
        # the same attribution role
        tokens = []
        for sentence in sentences:
            tokens += sentence['tokens']

        # Now we can group tokens according to attribution role
        token_groups = []
        group = []
        prev_role = None
        for token in tokens:

            # Get this token's role relative to the focal attribution
            role = cls.get_token_roles(token, attribution)

            # Was there a role-change?
            if role != prev_role:

                # After a role change, store the tokens from last group
                if len(group) > 0:
                    token_groups.append((prev_role, group))

                # Start a new group
                group = []

            # Append the token to the group, and remember the role
            group.append(token)
            prev_role = role

        # Append the last group
        if len(group) > 0:
            token_groups.append((prev_role, group))

        return token_groups


    @staticmethod
    def get_token_roles(token, attribution):
        """
        Return the set of roles that this token has with respect to the
        supplied attribution.  Ignore roles relating to other attributions.
        """
        attr_id = attribution['id']
        if attr_id in token['attributions']:
            return token['attributions'][attr_id]
        else:
            return set()


    @staticmethod
    def get_sentences(attribution):

        # Get all the tokens directly involved in the attribution,
        # and use these to find the implicated sentences
        all_span_tokens = (
            attribution['cue'] + attribution['source'] 
            + attribution['content']
        )

        # Find all sentences that contain the involved tokens
        sentence_ids = attribution.get_sentence_ids()

        # Ensure we include any sentences arising between sentences
        # containing the attribution (Generally an attribution shouldn't
        # be able to gap whole sentences, but you never know)
        min_sent = min(sentence_ids) 
        max_sent = max(sentence_ids)+1
        sentences = attribution.document.sentences[min_sent:max_sent]

        return sentences


    @staticmethod
    def get_cue_head(attribution):
        # Find out what the head of the cue span is -- we want to give
        # it it's own styling
        try:
            cue_head = attribution.document._find_head(
                attribution['cue'])[0]
        except IndexError:
            cue_head = None
        return cue_head


    @staticmethod
    def get_source_head(attribution):
        # Find out what the head of the source span is -- we want to give
        # it it's own styling
        try:
            source_head = attribution.document._find_head(
                attribution['source'])[0]
        except IndexError:
            source_head = None
        return source_head


    @staticmethod
    def get_styles(
        additional_styling={},
        show_pos=True,
    ):
        # Work out styling for part-of-speech tags
        if show_pos:
            pos_style = {
                '.pos': {
                    'position': 'absolute', 'font-size': '0.6em',
                    'top': '6px', 'left': '50%', 'font-weight': 'normal',
                    'font-style': 'normal'
                },
                '.pos-inner': { 'position': 'relative', 'left': '-50%'}
            }
        else:
            pos_style = {'.pos': {'display': 'none'}}

        # Add default styling
        styles = {
            'body': {'line-height': '40px'},
            'p': {'margin-bottom': '30px', 'margin-top': '0'},
            '.role-cue': {'color': 'blue', 'text-decoration': 'underline'},
            '.role-source': {'color': 'blue', 'font-weight': 'bold'},
            '.role-content': {'color': 'blue', 'font-style': 'italic'},
            '.cue-head': {'border-bottom': '1px solid blue'},
            '.source-head': {'border-top': '1px solid blue'},
            '.token': {'position': 'relative'},
            '.attribution-id': {
                'display': 'block', 'font-size':'0.6em',
                'margin-bottom':'-20px'
            },
            '.daggar::before': {
                'content':'"*"', 'vertical-align':'super',
                'font-size':'0.8em'
            }
        }

        # Incorporate pos_style and additional styling option
        styles.update(pos_style)
        styles.update(additional_styling)

        # Make a style element
        return Styler(styles).as_element()


    @classmethod
    def get_head_element(
        cls,
        additional_styling={},
        show_pos=True,
        additional_head_elements=[]
    ):

        # Create a head element, this is what we'll build and return
        head = element('head')

        head.appendChild(cls.get_styles(additional_styling))

        # Apped any additional head elements passed in
        for additional_element in additional_head_elements:
            additional_head_elements.appendChild(additional_element)

        return head


    @classmethod
    def wrap_as_html_page(
        cls,
        body_content,
        additional_styling='',
        show_pos=True,
        additional_head_elements=''
    ):
        """
        Deprecated.  Still used by
        `validators.crowdflower_task.display.get_results_html()`.
        """
        return (
            '<html>' 
            + cls.get_head_element(
                additional_styling, show_pos, additional_head_elements
            ).toprettyxml(indent='  ')
            + '<body>' + body_content + '</body>'
            + '</html>'
        )



class Styler(dict):

    def as_element(self):
        style_element = DOM.createElement('style')
        style_element.appendChild(text('\n' + self.serialize()))
        return style_element

    def serialize(self):
        string = ''
        for rule in self:

            # Open the style rule
            string += '%s {\n' % rule

            # Write each directive
            for directive in self[rule]:
                string += '\t%s: %s;\n' % (directive, self[rule][directive])

            # Close the style rule
            string += '}\n'

        return string


SUBSTITUTABLE_PRONOUNS = {'he', 'she', 'they'}
def is_substitutable_pronoun(token):
    return token['word'].lower() in SUBSTITUTABLE_PRONOUNS

