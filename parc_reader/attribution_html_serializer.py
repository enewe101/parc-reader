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


	def serialize_attributions(self, attributions, resolve_pronouns=False):
		'''
		This accepts an iterable of Attribution objects, and produces
		an HTML page that visualizes them.
		'''
		# Make a dom and basic top-level page structure
		dom, body = self.prepare_dom()
		for attribution in attributions:
			attribution_element = self.get_attribution_element(
				attribution, resolve_pronouns)
			body.appendChild(attribution_element)

		return dom.toprettyxml(indent='  ')


	def get_attribution_html(
		self, attribution, resolve_pronouns=False,
		indent='', newl=' '
	):
		attribution_element = self.get_attribution_element(
			attribution, resolve_pronouns)
		return attribution_element.toprettyxml(indent=indent, newl=newl)


	def get_attribution_element(self, attribution, resolve_pronouns=False):

		# Get the source and cue head so they can be specially highlighted
		cue_head = self.get_cue_head(attribution)
		source_head = self.get_source_head(attribution)

		# Group together tokens that are part of the same attribution role
		token_groups = self.group_tokens(attribution)

		# Make an element to contain the markup for this attribution
		attribution_element = div({'class':'attribution'})

		# Populate it with markup for all the tokens in this attribution
		for token_group in token_groups:
			token_group_element = self.make_token_group_element(
				token_group, resolve_pronouns, cue_head, source_head
			)
			attribution_element.appendChild(token_group_element)

		return attribution_element


	def prepare_dom(self, additional_styling={}):

		# Make a document, and put the basic elements in it
		dom = minidom.Document()
		html = dom.appendChild(dom.createElement('html'))
		html.appendChild(
			self.get_head_element(additional_styling=additional_styling))
		body = html.appendChild(dom.createElement('body'))

		return dom, body


	def make_token_group_element(
		self,
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
				if token['pos'] == 'PRP':
					resolved_element = self.make_resolved_element(
						token, cue_head, source_head)
					group_element.appendChild(resolved_element)
					continue

			# But usually we just make the element for each token
			token_element = self.make_token_element(
				token, cue_head, source_head)
			group_element.appendChild(token_element)

		return group_element


	def make_token_element(self, token, cue_head=None, source_head=None):

		# check if element is the cue head or source head, and adjust 
		# token element's class accordingly
		attrs = {'class':'token'}
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


	def make_resolved_element(self, token, cue_head=None, source_head=None):

		# Get the representative mention for the token, if any
		resolved_tokens = self.substitute_pronoun_token(token)

		# If a representative element was found, make the html representing
		# it, leaving a stylable div wrapping the replacement text so
		# it can be visualized
		if resolved_tokens is not None:
			resolved_element = span({'class':'pronoun'})
			for resolved_token in resolved_tokens:
				token_element = self.make_token_element(
					resolved_token, cue_head, source_head)
				resolved_element.appendChild(token_element)

		# Otherwise, just get the element for the original token
		else:
			resolved_element = self.make_token_element(token)

		# Return the element, whether reprsenting replacement or original
		return resolved_element
	

	def substitute_pronoun_token(self, token):

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


	def group_tokens(self, attribution):

		# Get the sentences involved in the attribution
		sentences = self.get_sentences(attribution)

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
			role = self.get_token_role(token, attribution)

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


	def get_token_role(self, token, attribution):

		# Ignore roles for the tokens in other attributions
		if token['attribution'] is not None:
			if token['attribution']['id'] != attribution['id']:
				return None

		# Normally just return the token's role
		return token['role']


	def get_sentences(self, attribution):

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


	def get_cue_head(self, attribution):
		# Find out what the head of the cue span is -- we want to give
		# it it's own styling
		try:
			cue_head = attribution.document._find_head(
				attribution['cue'])[0]
		except IndexError:
			cue_head = None
		return cue_head


	def get_source_head(self, attribution):
		# Find out what the head of the source span is -- we want to give
		# it it's own styling
		try:
			source_head = attribution.document._find_head(
				attribution['source'])[0]
		except IndexError:
			source_head = None
		return source_head


	def get_head_element(
		self, 
		additional_styling={},
		show_pos=True,
		additional_head_elements=[]
	):

		# Create a head element, this is what we'll build and return
		head = element('head')

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
		style_element = Styler(styles).as_element()
		head.appendChild(style_element)

		# Apped any additional head elements passed in
		for additional_element in additional_head_elements:
			additional_head_elements.appendChild(additional_element)

		return head


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


#	def wrap_as_html_page(
#		self,
#		body_content,
#		additional_styling='',
#		show_pos=True,
#		additional_head_elements=''
#	):
#		return (
#			'<html>' 
#			+ self.get_head_element(
#				additional_styling, show_pos, additional_head_elements) 
#			+ '<body>' + body_content + '</body>'
#			+ '</html>'
#		)
#
#
#
#
#	def get_attribution_html(self, attribution):
#		'''
#		given an attribution, write out the sentence as text, with the
#		attribution highlighted in color
#		'''
#
#		# Keep this attribution's id, this ensures we only highlight
#		# the roles for the given attribution (since multiple attributions
#		# can arise in the same tokens, and overlap)
#		attribution_id = attribution['id']
#
#		# Find out what the head of the cue span is -- we want to give
#		# it it's own styling
#		try:
#			cue_head = self._find_head(attribution['cue'])[0]
#		except IndexError:
#			cue_head = None
#
#		# Find out what the head of the source span is -- we want to give
#		# it it's own styling
#		try:
#			source_head = self._find_head(attribution['source'])[0]
#		except IndexError:
#			source_head = None
#
#		# First, get the sentence(s) involved in the attribution
#		# (and their tokens)
#		all_span_tokens = (
#			attribution['cue'] + attribution['source'] 
#			+ attribution['content'])
#		sentence_ids = attribution.get_sentence_ids()
#		#sentence_ids = [t['sentence_id'] for t in all_span_tokens]
#		sentences = self.sentences[min(sentence_ids) : max(sentence_ids)+1]
#		tokens = []
#		for sentence in sentences:
#			tokens += sentence['tokens']
#
#		words = ''
#		previous_role = None
#		for token in tokens:
#
#			# If the token is part of the target attribution, 
#			# Resolve the current token's role
#			role = None
#			if token['attribution'] is not None:
#				if token['attribution']['id'] == attribution_id:
#					role = token['role']
#
#			# If we have a change in role, close the old role (if any)
#			# and open the new one (if any)
#			if previous_role != role:
#
#				# Close the old role, if any
#				if previous_role is not None:
#					this_word = '</span> '
#				else:
#					this_word = ' '
#
#				# Open the new role, if any
#				if role is not None:
#					this_word = (
#						this_word + '<span class="quote-%s">' % role)
#
#			else:
#				this_word = ' '
#
#			# Finally add this token's word itself
#			# If the token is the head of the cue phrase, style accordingly
#			if token is cue_head:
#				this_word = (
#					this_word + '<span class="token cue-head">'
#					+ self.transform_word(token, role)
#					+ '<span class="pos"><span class="pos-inner">'
#					+ token['pos'] + '</span></span>'
#					+ '</span>'
#				)
#
#			elif token is source_head:
#				this_word = (
#					this_word + '<span class="token source-head">'
#					+ self.transform_word(token, role)
#					+ '<span class="pos"><span class="pos-inner">'
#					+ token['pos'] + '</span></span>' 
#					+ '</span>'
#				)
#
#			else:
#				this_word = (
#					this_word 
#					+ '<span class="token">'
#					+ self.transform_word(token, role)
#					+ '<span class="pos"><span class="pos-inner">'
#					+ token['pos'] + '</span></span>'
#					+ '</span>'
#				)
#
#			# Add this word on to the words collected so far.
#			words += this_word
#
#			# Update the previous role
#			previous_role = role
#
#		# We have finished the sentences.  Close the last role if any.
#		if previous_role is not None:
#			words += '</span>'
#
#		return words
#
#
#	def transform_word(
#		self,
#		token,
#		role,
#		mark_pronouns=True,
#		resolve_pronouns=False
#	):
#		'''
#		Provides additional token-specific transformations for the HTML
#		display of the token.  
#		
#		If `mark_pronouns` is true, add an asterisk to the pronouns that
#		occur in sources.
#
#		If `resolve_pronouns` is true, the substitute the representative
#		mention for the pronoun, if available.
#		'''
#
#		if role is 'source' and token['pos'] in ['PRP', 'PRP$']:
#			if mark_pronouns:
#				return token['word'] + '<span class="daggar"></span>'
#
#			elif resolve_pronouns:
#
#				if len(token['mentions']) > 0:
#					ref = token['mentions'][0]['reference']
#					representative_tokens = ref['representative']['tokens']
#					sub_tokens = [
#						t['word']+'('+token['role']+')' 
#						for t in representative_tokens
#					]
#
#				else:
#					tokens.append(
#						token['word']+'('+token['pos']+')'
#						+'('+token['role']+')'
#					)   
#
#
#		else:
#			return token['word']
#
