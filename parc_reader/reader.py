from xml.dom import minidom
from parc_reader.utils import IncrementingMap as IncMap, rangify
from bs4 import BeautifulSoup as Soup
from corenlp_xml_reader.annotated_text import (
	AnnotatedText as CorenlpAnnotatedText, Token
)
from itertools import izip_longest
from collections import defaultdict
import re


ROLES = {'cue', 'content', 'source'}
WHITESPACE_MATCHER = re.compile(r'\s+')


# Errors that can be raised by ParcCorenlpReader
class ParcCorenlpReaderException(Exception):
	pass
class AlignmentError(ParcCorenlpReaderException):
	pass


class ParcCorenlpReader(object):

	def __init__(
		self, 
		corenlp_xml, 
		parc_xml=None, 
		raw_txt=None,
		aida_json=None, 
		corenlp_options={},
		parc_options={}
	):

		# Own the raw text and the id prefix
		self.raw_txt = raw_txt

		# Construct the corenlp datastructure
		self.core = CorenlpAnnotatedText(
			corenlp_xml, aida_json, **corenlp_options
		)

		# Construct the parc datastructure if parc_xml was supplied
		self.parc = None
		if parc_xml is not None:
			self.parc = ParcAnnotatedText(
				parc_xml, include_nested=False,
				**parc_options
			)

		# Align the datastructures
		self.sentences = []

		# If we have a parc datastructure, we'll merge it with the corenlp
		# datastructure now
		if self.parc is not None:
			self.merge()

		# Otherwise, we'll just put placeholders for parc properties in
		# the corenlp datastructure
		else:
			self.blank_merge()

		# Determine where paragraph breaks should go
		if self.raw_txt is not None:
			self.delineate_paragraphs()

		# Initialize an incrementing integer, used for generating new
		# attribution ids
		self.incrementing_integer = 0


	def get_parc_xml(self, indent='  '):
		xml_dom = self.create_xml_dom()
		return xml_dom.toprettyxml(indent=indent)


	def create_xml_dom(self):

		# Make a document and a root element
		doc = minidom.Document()
		root = doc.createElement('root')
		doc.appendChild(root)

		# Make an element for every sentence tag
		gorn = 0
		word = 0
		for sentence in self.sentences:

			sentence_word = 0	# keeps track of token index w/in sentence

			# First get the top (sentence) tag (bypass the root tag)
			sentence_constituent = sentence['c_root']['c_children'][0]

			# Recursively build the sentence tag (with all constituent
			# and word tags)
			root_sentence_xml_tag = doc.createElement('SENTENCE')
			root_sentence_xml_tag.setAttribute('gorn', str(gorn))
			sentence_xml_tag, word, sentence_word = (
				self.create_sentence_tag(
					doc, sentence_constituent, word=word, 
					sentence_word=sentence_word, gorn_trail=(), gorn=gorn
				)
			)
			root_sentence_xml_tag.appendChild(sentence_xml_tag)
			gorn += 1

			# Append the sentence tag to the growing document
			root.appendChild(root_sentence_xml_tag)

		return doc


	def create_sentence_tag(
		self,
		doc,
		constituent,
		word=0,
		sentence_word=0,
		gorn_trail=(),
		gorn=0
	):

		# Is this a compund constituent, or a token?
		is_token = False
		if len(constituent['c_children']) == 0:
			is_token = True

		# Create the xml tag for this constituent
		if is_token:
			element = doc.createElement('WORD')
			element.setAttribute(
				'ByteCount', '%s,%s' % (
				constituent['character_offset_begin'],
				constituent['character_offset_end'])
			)
			element.setAttribute('lemma', constituent['lemma'])
			element.setAttribute('pos', constituent['pos'])
			element.setAttribute('text', constituent['word'])
			element.setAttribute('gorn', self.gorn_str(gorn_trail, gorn))
			element.setAttribute('word', str(word))
			element.setAttribute('sentenceWord', str(sentence_word))
			word += 1
			sentence_word += 1

			if constituent['attribution'] is not None:
				attribution = doc.createElement('attribution')
				attribution.setAttribute(
					'id', constituent['attribution']['id']
				)
				attribution_role = doc.createElement('attributionRole')
				attribution_role.setAttribute(
					'roleValue', constituent['role'])
				attribution.appendChild(attribution_role)
				element.appendChild(attribution)

			return element, word, sentence_word

		element = doc.createElement(constituent['c_tag'])
		element.setAttribute('gorn', self.gorn_str(gorn_trail, gorn))

		# Create the child elements
		child_gorn = 0
		for child in constituent['c_children']:
			child_elm, word, sentence_word = self.create_sentence_tag(
				doc, child, word=word, sentence_word=sentence_word,
				gorn_trail=(gorn_trail + (gorn,)), gorn=child_gorn
			)
			element.appendChild(child_elm)
			child_gorn += 1

		return element, word, sentence_word


	def gorn_str(self, gorn_trail, gorn):
		return ','.join([str(g) for g in gorn_trail + (gorn,)])


	def __str__(self):
		return self.core.__str__()


	def wrap_as_html_page(
		self,
		body_content,
		additional_styling='',
		show_pos=True,
		additional_head_elements=''
	):
		return (
			'<html>' 
			+ self.get_html_head(
				additional_styling, show_pos, additional_head_elements) 
			+ '<body>' + body_content + '</body>'
			+ '</html>'
		)


	def get_html_head(self, additional_styling='', show_pos=True,
		additional_head_elements=''
	):
		if show_pos:
			pos_styling = ' '.join([
				'.pos {position: absolute; font-size: 0.6em;',
					'top: 6px; left: 50%; font-weight: normal;',
					'font-style: normal}',
				'.pos-inner {position: relative; left:-50%}',
			])
		else:
			pos_styling = '.pos {display: none;}'

		return ' '.join([
			'<head>',
			additional_head_elements,
			'<style>',
			'body {line-height: 40px;}',
			'p {margin-bottom: 30px; margin-top: 0}',
			'.quote-cue {color: blue; text-decoration: underline;}',
			'.quote-source {color: blue; font-weight: bold;}',
			'.quote-content {color: blue; font-style: italic;}',
			'.cue-head {border-bottom: 1px solid blue}',
			'.source-head {border-top: 1px solid blue}',
			'.token {position: relative}',
			'.attribution-id {display: block; font-size:0.6em;',
				'margin-bottom:-20px;}',
			'.daggar::before {content:"*"; vertical-align:super;',
				'font-size:0.8em;}',
			pos_styling,
			additional_styling,
			'</style></head>'
		])  


	def get_attribution_html(self, attribution):
		'''
		given an attribution, write out the sentence as text, with the
		attribution highlighted in color
		'''

		# Keep this attribution's id
		attribution_id = attribution['id']

		# Find out what the head of the cue span is -- we want to give
		# it it's own styling
		try:
			cue_head = self._find_head(attribution['cue'])[0]
		except IndexError:
			cue_head = None

		# Find out what the head of the source span is -- we want to give
		# it it's own styling
		try:
			source_head = self._find_head(attribution['source'])[0]
		except IndexError:
			source_head = None

		# First, get the sentence(s) involved in the attribution
		# (and their tokens)
		all_span_tokens = (
			attribution['cue'] + attribution['source'] 
			+ attribution['content'])
		sentence_ids = attribution.get_sentence_ids()
		#sentence_ids = [t['sentence_id'] for t in all_span_tokens]
		sentences = self.sentences[min(sentence_ids) : max(sentence_ids)+1]
		tokens = []
		for sentence in sentences:
			tokens += sentence['tokens']

		words = ''
		previous_role = None
		for token in tokens:

			# If the token is part of the target attribution, 
			# Resolve the current token's role
			role = None
			if token['attribution'] is not None:
				if token['attribution']['id'] == attribution_id:
					role = token['role']

			# If we have a change in role, close the old role (if any)
			# and open the new one (if any)
			if previous_role != role:

				# Close the old role, if any
				if previous_role is not None:
					this_word = '</span> '
				else:
					this_word = ' '

				# Open the new role, if any
				if role is not None:
					this_word = this_word + '<span class="quote-%s">' % role

			else:
				this_word = ' '

			# Finally add this token's word itself
			# If the token is the head of the cue phrase, style accordingly
			if token is cue_head:
				this_word = (
					this_word + '<span class="token cue-head">'
					+ self.transform_word(token, role)
					+ '<span class="pos"><span class="pos-inner">'
					+ token['pos'] + '</span></span>'
					+ '</span>'
				)

			elif token is source_head:
				this_word = (
					this_word + '<span class="token source-head">'
					+ self.transform_word(token, role)
					+ '<span class="pos"><span class="pos-inner">'
					+ token['pos'] + '</span></span>' 
					+ '</span>'
				)

			else:
				this_word = (
					this_word 
					+ '<span class="token">'
					+ self.transform_word(token, role)
					+ '<span class="pos"><span class="pos-inner">'
					+ token['pos'] + '</span></span>'
					+ '</span>'
				)

			# Add this word on to the words collected so far.
			words += this_word

			# Update the previous role
			previous_role = role

		# We have finished the sentences.  Close the last role if any.
		if previous_role is not None:
			words += '</span>'

		return words


	def transform_word(self, token, role):
		'''
		Provides additional token-specific transformations for the HTML
		display of the token.  Currently this is only used to add an 
		asterisk to personal pronouns that arise in source role.
		'''

		if role is 'source' and token['pos'] in ['PRP', 'PRP$']:
			return token['word'] + '<span class="daggar"></span>'

		else:
			return token['word']




	def delineate_paragraphs(self):

		# A paragraph is just an array of CorenlpSentence objects
		self.paragraphs = []

		# Read the orignial raw text, and split it into its paragraphs
		paragraph_texts = self.raw_txt.strip().split('\n\n')

		# Collapse all whitespace out of the paragraphs.  This makes
		# aligning them to the sentences easier, because whitespace
		# does not consistently appear between tokens
		collapsed_paragraph_texts = [
			WHITESPACE_MATCHER.sub('', p) for p in paragraph_texts
		]

		sentence_pointer = 0
		last_excess = 0
		paragraph_idx = -1
		for collapsed_paragraph in collapsed_paragraph_texts:

			# We begin by assuming the paragraph consists of one sentence
			target_length = len(collapsed_paragraph)
			current_num_sentences = 1

			# Occasionally a paragraph break occurs within what was
			# considered one sentence in PARC.  This can happen when a 
			# heading is followed by a subheading.  If this paragraph
			# helps to make up for the excess of length in the last 
			# paragraph then that's probably what happened.  Skip it, and
			# deduct its length from the excess length.
			if last_excess - target_length >= 0:
				#print 'skipping!'
				last_excess -= target_length
				continue

			# But if we run out of sentences, then there's no more 
			# paragraphs to make, so break!
			try:
				current_length = self.get_collapsed_length(sentence_pointer)
			except IndexError:
				break

			closest_length = current_length
			closest_distance = abs(target_length - current_length)
			best_num_sentences = 1

			# Continually include more sentences, until we exceed the
			# target length of the paragraph.  Keep track of how many
			# sentences gave the closest length to that of the paragraph
			while current_length <= target_length:

				# Try adding another sentence to this paragraph.
				# but if we run out of sentences, break.
				current_num_sentences += 1
				try:
					current_length += self.get_collapsed_length(
						sentence_pointer + current_num_sentences - 1
					)
				except IndexError:
					break

				# How close is the length of the paragraph with this 
				# many sentences?  If its the closest so far, record it.
				current_distance = abs(target_length - current_length)
				if current_distance < closest_distance:
					closest_length = current_length
					closest_distance = current_distance
					best_num_sentences = current_num_sentences

			# Now put the correct number of sentences into the paragraph,
			# and store this paragraph in the article object's global list
			paragraph_idx += 1
			this_paragraph = []
			add_sentences = self.sentences[
				sentence_pointer : sentence_pointer + best_num_sentences
			]
			for sentence in add_sentences:
				sentence['paragraph_idx'] = paragraph_idx
				this_paragraph.append(sentence)
			self.paragraphs.append(this_paragraph)

			# Advance the sentence pointer according to how many sentences
			# were aligned to the last paragraph
			sentence_pointer += best_num_sentences

			# If the paragraph we built was too big, it may be because
			# PARC glues multiple paragraphs together (because the 
			# "paragraphs" in the original are just sentence fragments and
			# we won't split paragraphs within sentence fragments).
			# Keep track of this so that we can skip these fragmentary 
			# "paragraphs" as needed.
			last_excess = closest_length - target_length

			#if (
			#	closest_length - target_length > 12 
			#	or closest_length - target_length < 0
			#):
			#print closest_length - target_length
			#print '---'
			#print len(collapsed_paragraph)
			#print collapsed_paragraph
			#print '---'
			#print closest_length
			#print ''.join([
			#	''.join([t['word'] for t in sentence['tokens']])
			#	for sentence in this_paragraph
			#])
			#print '\n'
			#	raise AlignmentError


		# If there's sentences left over, add them to the last paragraph
		additional_sentences = self.sentences[sentence_pointer:]
		for sentence in additional_sentences:
			this_paragraph.append(sentence)
			sentence['paragraph_idx'] = paragraph_idx


	def _find_head(self, tokens):

		heads = []

		# If there is only one token, that's the head
		if len(tokens) ==  1:
			heads = [tokens[0]]

		else:

			# otherwise iterate over all the tokens to find the head
			for token in tokens:

				# if this token has no parents or children its not part
				# of the dependency tree (it's a preposition, e.g.)
				if 'parents' not in token and 'children' not in token:
					continue

				# if this token has any parents that among the tokens list
				# it's not the head!
				try:

					token_ids = [
						(t['sentence_id'], t['id']) for t in tokens
					]

					has_parent_in_span = any([
						(t[1]['sentence_id'], t[1]['id'])
						in token_ids for t in token['parents']
					])

					if has_parent_in_span:
						relations_to_parents = [
							t for t in token['parents'] if t[1] in tokens
						]
						continue
				except KeyError:
					pass

				# otherwise it is the head
				else:
					heads.append(token)

		# NOTE: head may be none
		return heads


	def get_collapsed_length(self, sentence_num):
		# Get this sentence's tokens
		tokens = self.sentences[sentence_num]['tokens']
		# Concatenate them and calculate the total length
		return len(''.join([t['word'] for t in tokens]))


	def get_attribution_id(self, id_formatter):
		'''
		Provides an attribution id that is guaranteed to be unique
		within object instances using an incrementing integer.  The integer
		is appended onto the id_formatter.
		'''
		self.incrementing_integer += 1
		try:
			return id_formatter % (self.incrementing_integer - 1)
		except TypeError:
			return id_formatter + str(self.incrementing_integer - 1)


	def remove_attribution(self, attribution_id):
		'''
		Deletes the attribution identified by attribution_id, including
		all references from sentences, tokens, and globally
		'''
		attribution = self.attributions[attribution_id]

		# first remove the attribution from each of the tokens
		sentence_ids = set()
		tokens = (
			attribution['cue'] + attribution['content'] 
			+ attribution['source']
		)
		for token in tokens:
			sentence_ids.add(token['sentence_id'])
			token['role'] = None
			token['attribution'] = None

		# Delete references to the attribution on sentences
		for sentence_id in sentence_ids:
			sentence = self.sentences[sentence_id]
			del sentence['attributions'][attribution_id]

		# Delete the global reference to the attribution
		del self.attributions[attribution_id]


	def add_attribution(
		self, 
		cue_tokens=[], 
		content_tokens=[], 
		source_tokens=[], 
		attribution_id=None,
		id_formatter=''
	):
		'''
		Add a new attribution.  Create links from the sentences and tokens,
		involved, and make a reference on the global attributions list.
		'''

		# If no id was supplied, make one
		if attribution_id is None:

			# Ensure the id is unique
			while True:
				attribution_id = self.get_attribution_id(id_formatter)
				if attribution_id not in self.attributions:
					break

		if attribution_id in self.attributions:
			raise ValueError(
				'The attribution_id supplied is already in use: %s'
				% attribution_id
			)

		# Before proceeding, make sure that none of the tokens are already
		# part of an attribution.  This class currently doesn't support
		# tokens being part of multiple (i.e. nested) attributions
		tokens = cue_tokens + content_tokens + source_tokens
		for token in tokens:
			if (
				token['role'] is not None 
				or token['attribution'] is not None
			):
				raise ValueError(
					'Token(s) supplied for the attribution are already '
					'part of another attribution:\n' + str(token)
				)

		# Make a new empty attribution having correct id
		new_attribution = Attribution({
			'id':attribution_id, 'cue':[], 'content':[], 'source':[]
		})

		# Put a reference in the global attributions list
		self.attributions[attribution_id] = new_attribution

		# Ensure each of the tokens involved in the attribution gets
		# a reference to the attribution and gets labelled with the 
		# correct role.  We also ensure that each sentence involved
		# in the attribution gets a reference to the attribution
		self.add_to_attribution(new_attribution, 'cue', cue_tokens)
		self.add_to_attribution(new_attribution, 'content', content_tokens)
		self.add_to_attribution(new_attribution, 'source', source_tokens)

		return new_attribution


	def add_to_attribution(self, attribution, role, tokens):
		'''
		Add the given tokens to the given attribution using the given
		role (which should be 'cue', 'content', or 'source'. 
		'''

		# Verify that the attribution is actually an Attribution
		if not isinstance(attribution, Attribution):
			raise ValueError(
				'supplied attribution must be of type Attribution.')

		# We'll go through each token, ensuring it has a reference to the
		# attribution and knows its role.  At the same time, we'll 
		# accumulate references to the sentence(s) they belong to (normally
		# just one sentence, but sometimes multiple).
		sentence_ids = set()
		for token in tokens:

			# Verify that the tokens are actually Tokens
			if not isinstance(token, Token):
				raise ValueError(
					'`tokens` must be an iterable of objects of type '
					'Token.'
				)

			# Copy the role and attribution onto the token
			token['role'] = role
			token['attribution'] = attribution
			sentence_ids.add(token['sentence_id'])

			# Copy the token to the attribution
			attribution[role].append(token)

		# Now ensure each sentence has a reference to the attribution
		attribution_id = attribution['id']
		for sentence_id in sentence_ids:
			sentence = self.sentences[sentence_id]
			sentence['attributions'][attribution_id] = attribution


	def blank_merge(self):
		'''
		This is called instead of merge when there is no parc datastructure
		to be merged with the corenlp datastructure.  Instead, it just
		adds the parc properties into the datastructure, filling them 
		with None's and empty dictionaries.  This makes it possible to
		add new attributions to the datastructure.
		'''
		self.attributions = {}
		for sentence in self.core.sentences:
			self.sentences.append(sentence)
			sentence['attributions'] = {}
			for token in sentence['tokens']:
				token['role'] = None
				token['attribution'] = None


	def merge(self):
		'''
		This merges information from CoreNLP with information from the
		Parc annotations, while assuming that they have identical 
		tokenization and sentence spliting (which makes alignment trivial).
		'''
		self.attributions = {}
		aligned_sentences = zip(self.core.sentences, self.parc.sentences)
		for core_sentence, parc_sentence in aligned_sentences:

			# We'll build the aligned sentence off the corenlp sentence
			self.sentences.append(core_sentence)
			core_sentence['attributions'] = {}

			# Gather the attributions that exist on this sentence
			for attribution in parc_sentence['attributions']:

				_id = attribution['id']

				# It's possible that attributions span multiple sentences,
				# so if we've seen this attribution in a previous sentence,
				# get a reference to it
				if _id in self.attributions:
					new_attribution = self.attributions[_id]

				# Otherwise build the attribution, and add it to the global
				# list of attributions for the article.
				else:
					new_attribution = Attribution({
						'id':_id, 'content':[], 'cue':[], 'source':[]
					})
					self.attributions[_id] = new_attribution

				# Add the attribution to the list for this sentence
				core_sentence['attributions'][_id] = new_attribution

				# Populate the attribution spans with actual 
				# tokens (they are currently just index ranges).  We'll
				# populate them with corenlp's tokens
				for role in ROLES:
					for span in attribution[role]:

						# replace attribution index spans with actual
						# tokens
						new_attribution[role].extend(get_spans(
							core_sentence, attribution[role], 
							elipsis=False
						))

			# We'll merge information from parc tokens onto core_nlp tokens
			aligned_tokens = zip(
				core_sentence['tokens'], parc_sentence['tokens']
			)

			# Specifically, we'll copy attribution membership information 
			# from parc tokens onto core_tokens.
			for core_token, parc_token in aligned_tokens:
				if 'attribution_id' in parc_token:
					_id = parc_token['attribution_id']
					try:
						core_token['attribution'] = (
							core_sentence['attributions'][_id])
					except KeyError:
						print core_sentence['attributions']

					core_token['role'] = parc_token['role']
				else:
					core_token['attribution'] = None
					core_token['role'] = None


class Attribution(dict):

	def get_sentence_ids(self):
		all_span_tokens = self['cue'] + self['source'] + self['content']
		sentence_ids = {t['sentence_id'] for t in all_span_tokens}
		return sentence_ids



# This class was an initial approach to align CoreNLP annotations to PARC
# annotations when their tokenizations and sentence splitting were not 
# identical.  However, CoreNLP annotations have since been done with 
# identical tokenization and sentence splitting, so this has been replaced
# by the simpler ParcCorenlpReader which doesn't worry about token 
# alignments
#
#class ParcCorenlpAligner(object):
#
#	def __init__(
#		self, 
#		parc_xml, 
#		corenlp_xml, 
#		raw_txt=None,
#		aida_json=None, 
#		corenlp_options={},
#		parc_options={}
#	):
#		
#		# Reconstruct the parc and corenlp datastructures
#		self.parc = ParcAnnotatedText(
#			parc_xml, include_nested=False,
#			**parc_options
#		)
#		self.core = CorenlpAnnotatedText(
#			corenlp_xml, aida_json, **corenlp_options
#		)
#
#		# Align the datastructures
#		#self.diagnose_align()
#		self.align()
#
#
#	def next_parc_token(self):
#		'''
#		Gets the next token, internally advancing the token and sentence
#		pointers.
#		'''
#
#		# Try advancing the token pointer
#		self.parc_token_ptr += 1
#		try:
#			token = self.parc_sentence['tokens'][self.parc_token_ptr]
#
#		# If we exceed the tokens list, try advancing the sentence pointer
#		except IndexError:
#			self.parc_sentence_ptr += 1
#			self.parc_token_ptr = 0
#			try:
#				self.parc_sentence = self.parc.sentences[
#					self.parc_sentence_ptr]
#
#			# If we exceed the sentences list, return `None`
#			except IndexError:
#				token = None
#			else:
#				token = self.parc_sentence['tokens'][self.parc_token_ptr]
#
#		return None if token is None else token['word']
#
#
#	def next_core_token(self):
#		'''
#		Gets the next token in the corenlp datastructure, internally 
#		advancing the token and sentence pointers
#		'''
#
#		# Try advancing the token pointer
#		self.core_token_ptr += 1
#		try:
#			token = self.core_sentence['tokens'][self.core_token_ptr]
#
#		# If we exceed the tokens list, try advancing the sentence pointer
#		except IndexError:
#			self.core_sentence_ptr += 1
#			self.core_token_ptr = 0
#			try:
#				self.core_sentence = self.core.sentences[
#					self.core_sentence_ptr]
#
#			# If we exceed the sentences list, return `None`
#			except IndexError:
#				token = None
#			else:
#				token = self.core_sentence['tokens'][self.core_token_ptr]
#
#		# Return the original `word` property as the token's representation
#		return None if token is None else token['word']
#
#
#	def peek_ahead_core(self, advance_by):
#		'''
#		Gets the token that follows the current one by `advance_by` 
#		positions, without advancing the internal pointer.
#		'''
#
#		# Copy pointers locally
#		core_token_ptr = self.core_token_ptr
#		core_sentence_ptr = self.core_sentence_ptr
#		core_sentence = self.core.sentences[core_sentence_ptr]
#
#		for i in range(advance_by):
#
#			# Try advancing the token pointer
#			core_token_ptr += 1
#			try:
#				token = core_sentence['tokens'][core_token_ptr]
#
#			# If we exceed the tokens list, try advancing the sentence ptr
#			except IndexError:
#				core_sentence_ptr += 1
#				core_token_ptr = 0
#				try:
#					core_sentence = self.core.sentences[
#						core_sentence_ptr]
#
#				# If we exceed the sentences list, return `None`
#				except IndexError:
#					token = None
#				else:
#					token = core_sentence['tokens'][core_token_ptr]
#
#		# Return the original `word` property 
#		return None if token is None else token['word']
#
#
#	def peek_ahead_parc(self, advance_by):
#		'''
#		Gets the token that follows the current one by `advance_by` 
#		positions, without advancing the internal pointer.
#		'''
#
#		# Copy pointers locally
#		parc_token_ptr = self.parc_token_ptr
#		parc_sentence_ptr = self.parc_sentence_ptr
#		parc_sentence = self.parc.sentences[parc_sentence_ptr]
#
#		for i in range(advance_by):
#
#			# Try advancing the token pointer
#			parc_token_ptr += 1
#			try:
#				token = parc_sentence['tokens'][parc_token_ptr]
#
#			# If we exceed the tokens list, try advancing the sentence ptr
#			except IndexError:
#				parc_sentence_ptr += 1
#				parc_token_ptr = 0
#				try:
#					parc_sentence = self.parc.sentences[
#						parc_sentence_ptr]
#
#				# If we exceed the sentences list, return `None`
#				except IndexError:
#					token = None
#				else:
#					token = parc_sentence['tokens'][parc_token_ptr]
#
#		# Return the original `word` property 
#		return None if token is None else token['word']
#	
#
#	def reset_pointers(self):
#
#		self.core_sentence_ptr = 0
#		self.parc_sentence_ptr = 0
#		self.core_token_ptr = 0
#		self.parc_token_ptr = 0
#
#		self.core_sentence = self.core.sentences[0]
#		self.parc_sentence = self.parc.sentences[0]
#
#
#	def _align_current_tokens(self):
#
#		core_pos = (self.core_sentence_ptr, self.core_token_ptr)
#		parc_pos = (self.parc_sentence_ptr, self.parc_token_ptr)
#
#		self.core2parc[core_pos].append(parc_pos)
#		self.parc2core[parc_pos].append(core_pos)
#
#
#
#	def align(self):
#
#		self.reset_pointers()
#		self.core2parc = defaultdict(list)
#		self.parc2core = defaultdict(list)
#
#		# We'll go token by token, aligning the two datastructures.
#		# We'll break out of this loop when one data structure is exhausted
#		# (usually both are exhausted at the same time)
#		while True:
#
#			core_token = self.next_core_token()
#			parc_token = self.next_parc_token()
#
#			# Both datastructures are exhausted when we get back None
#			# for both tokens
#			if core_token is None or parc_token is None:
#				break
#
#			# If the tokens match, note the alignment
#			if core_token == parc_token:
#				self._align_current_tokens()
#
#			# Otherwise, maybe CoreNLP split a token that parc did not
#			elif self.peek_ahead_core(2) == self.peek_ahead_parc(1):
#				print '%s\t->\t%s' % (core_token, parc_token)
#				self._align_current_tokens()
#				core_token = self.next_core_token()
#				print '\t%s\t->\t%s' % (core_token, parc_token)
#				self._align_current_tokens()
#
#			# Or, maybe parc split a token that corenlp did not
#			elif self.peek_ahead_core(1) == self.peek_ahead_parc(2):
#				print '%s\t->\t%s' % (core_token, parc_token)
#				self._align_current_tokens()
#				parc_token = self.next_parc_token()
#				print '\t%s\t->\t%s' % (core_token, parc_token)
#				self._align_current_tokens()
#
#			# Or, maybe they just didn't quite spell the tokens the same
#			elif self.peek_ahead_core(1) == self.peek_ahead_parc(1):
#				print '%s\t->\t%s' % (core_token, parc_token)
#				self._align_current_tokens()
#
#			# Otherwise, we're in a more difficult situation.
#			# For now, we give up on such situations after printing a 
#			# diagnostic
#			else:
#				self.print_diagnostic(
#					self.core_sentence_ptr, self.parc_sentence_ptr
#				)
#				self.print_diagnostic(
#					self.core_sentence_ptr+1, self.parc_sentence_ptr+1
#				)
#
#				raise AlignmentError
#
#	def print_diagnostic(self, core_sentence_ptr, parc_sentence_ptr):
#
#		try:
#			core_sentence = self.core.sentences[core_sentence_ptr]
#		except IndexError:
#			core_sentence = {'tokens':[]}
#
#		try:
#			parc_sentence = self.parc.sentences[parc_sentence_ptr]
#		except IndexError:
#			parc_sentence = {'tokens':[]}
#
#		core_tokens = [t['word'] for t in core_sentence['tokens']]
#		parc_tokens = [t['word'] for t in parc_sentence['tokens']]
#		token_pairs = izip_longest(core_tokens, parc_tokens)
#		for core_token, parc_token in token_pairs:
#			print core_token, parc_token
#
#
#	def diagnose_align(self):
#		sentence_pairs = izip_longest(
#			self.core.sentences, self.parc.sentences
#		)
#		for core_sentence, parc_sentence in sentence_pairs:
#
#			if core_sentence is None:
#				core_sentence = {'tokens':[]}
#			if parc_sentence is None:
#				parc_sentence = {'tokens':[]}
#
#			core_len = len(core_sentence['tokens'])
#			parc_len = len(parc_sentence['tokens'])
#			print core_len, parc_len
#
#			if core_len != parc_len:
#
#				core_tokens = [
#					t['word'] for t in 
#					core_sentence['tokens']
#				]
#				parc_tokens = [
#					t['word'] for t in 
#					parc_sentence['tokens']
#				]
#				paired_tokens = izip_longest(core_tokens, parc_tokens)
#				alignment_trace = ''
#				for core_token, parc_token in paired_tokens:
#					alignment_trace += '%s %s\n' % (core_token, parc_token)
#
#				raise AlignmentError(alignment_trace)



# This reads parc files and builds a coherent representation of attribuions
# It's the PARC equivalent for the corenlp_xml_reader.  It's used by the
# ParcCorenlpReader to read parc files before merging the info contained
# therein with the info from corenlp.
class ParcAnnotatedText(object):
	'''
	Class that represents the contents of a PARC annotated article file
	using convenient python types.
	'''

	def __init__(self, parc_xml, include_nested=True):
		'''
		Provide the raw xml for a PARC annotated article file as the 
		first argument.  If include_nested is `True`, then nested 
		attributions will be read and included in the representation.  If
		false, nested attributions will be skipped.  When nested 
		attributions are skipped, then, among attributions that compete
		to include the same token(s) in their span, only one will be kept
		in the final representation: whichever one occurs textually first
		in the PARC file.
		'''

		self.include_nested = include_nested
		soup = Soup(parc_xml, 'html.parser')
		self.sentences = []
		sentence_tags = soup.find_all('sentence')

		for sentence_tag in sentence_tags:

			sentence = ParcSentence(
				{'tokens':[], 'attributions':{}}
			)
			self.sentences.append(sentence)
			word_tags = sentence_tag.find_all('word')
			current_attribution_spans = {}
			attribution_priority = IncMap()
			conflict_sets = set()
			for word_id, word_tag in enumerate(word_tags):

				token = {
					'word': unescape(word_tag['text']),
					'pos': word_tag['pos'],
					'lemma': word_tag['lemma']
				}

				attributions = word_tag.find_all('attribution')
				viable_attributions = []
				for attribution in attributions:

					# Get the info characterizing this token's role in this
					# attribution
					role = attribution.find('attributionrole')['rolevalue']
					_id = attribution['id']

					# Keep track of the viable attributions that are 
					# competing for this word.  This is important if 
					# include nested is false, because then we allow only 
					# one attribution to "own" a token.  We can also
					# pre-emptively eliminated attributions explicitly 
					# flagged as nested
					if 'Nested' in _id:
						continue
					viable_attributions.append(_id)

					# Keep track of the order in which attributions were
					# initially encountered
					attribution_priority.add(_id)

					if _id not in current_attribution_spans:
						current_attribution_spans[_id] = {
							'id': _id,
							'cue':[], 'content':[], 'source':[]
						}

					# Add this word (referenced by its id) to this role
					# of this attribution
					current_attribution_spans[_id][role].append(word_id)

				# If more than one viable attribution is assigned to this 
				# word, note the potential conflict.  If nested attributions
				# are not allowed, then these are indeed conflicts and will
				# need to be resolved
				if len(viable_attributions) > 1:
					conflict_sets.add(tuple(viable_attributions))

				sentence['tokens'].append(token)

			# If we don't want to include nested attributions, then we
			# will now resolve conflicts where words have been found 
			# belonging to multiple attributions
			if not self.include_nested:
				for conflict_set in conflict_sets:
					# Filter ids in the conflict set that are still viable
					viable_ids = [
						_id for _id in conflict_set 
						if _id in current_attribution_spans
					]

					# Sort viable attribution_ids into the order in which
					# they were first encountered
					viable_ids.sort(
						key=lambda _id: attribution_priority[_id]
					)

					# Delete all but the highest priority attribution
					for _id in viable_ids[1:]:
						del current_attribution_spans[_id]


			# TODO: put attributions onto the tokens
			for _id in current_attribution_spans:
				for role in ROLES:
					for token_id in current_attribution_spans[_id][role]:
						sentence['tokens'][token_id]['role'] = role
						sentence['tokens'][token_id]['attribution_id'] = (
							_id)
						sentence['tokens'][token_id]['attribution'] = (
							current_attribution_spans[_id]
						)


			# Currently the spans in attributions are just lists of 
			# token ids.  Group together contigous ids using a 
			# (start, stop) notation compatible with the range() function
			for _id in current_attribution_spans:
				for role in ROLES:
					current_attribution_spans[_id][role] = rangify(
						current_attribution_spans[_id][role]
					)

			# Add the rangified attribution spans
			sentence['attributions'] = current_attribution_spans.values()



class ParcSentence(dict):

	# Use the global function, but bind self as the sentence
	def get_spans(self, spans, elipsis=True):
		get_spans(self, spans, elipsis=elipsis)


	def get_cue(self, attribution_idx=0):
		attribution = self['attributions'][attribution_idx]
		return self.get_spans(attribution['cue'])

	def get_content(self, attribution_idx=0):
		try:
			attribution = self['attributions'][attribution_idx]
			return self.get_spans(attribution['content'])
		except TypeError:
			raise Exception

	def get_source(self, attribution_idx=0):
		attribution = self['attributions'][attribution_idx]
		return self.get_spans(attribution['source'])



def unescape(token):
	'''
	Reverses token escaping that has been done in PARC3
	'''

	# Restore round and square brackets
	if token == '-LRB-':
		return '('
	if token == '-RRB-':
		return ')'
	if token == '-RCB-':
		return ']'
	if token == '-LCB-':
		return '['

	# Finally, remove any backslashes, which are used to escape what
	# parc considers to be special characters, but which should be 
	# printed literally
	return token.replace('\\', '')



def get_span(sentence, start, stop):
	return sentence['tokens'][start:stop]



def get_spans(sentence, spans, elipsis=True):
	'''
	This function retrieves the tokens for a given list of 
	spans.  A span is a contiguous range of tokens, and a list of
	spans contains one or more contiguous range of tokens.  

	When retrieving tokens for a list of spans that contains ore than
	one span, we visually indicate the discontinuity that exists 
	between spans, by adding a false token that looks like an elepsis
	'''
	tokens = []
	first = True
	for span in spans:

		# We add an elipses false token to visually show that 
		# a discontinuity exists between two spans.
		if first:
			first = False
		elif elipsis:
			tokens.append(
				{'word':'...'}
			)

		# Collect the tokens represented by the span
		try:
			tokens.extend(get_span(sentence, *span))
		except TypeError:
			print span
			raise

	return tokens
