from collections import OrderedDict
from xml.dom import minidom
from parc_reader.utils import get_spans
from parc_reader.attribution import Attribution
from corenlp_xml_reader.annotated_text import (
	AnnotatedText as CorenlpAnnotatedText, Token
)
from attribution_html_serializer import AttributionHtmlSerializer
from parc_reader.parc_annotated_text import ParcAnnotatedText
import re


ROLES = {'cue', 'content', 'source'}
WHITESPACE_MATCHER = re.compile(r'\s+')


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


	def get_attribution_html(self, attribution, resolve_pronouns=False):
		serializer = AttributionHtmlSerializer()
		return serializer.get_attribution_html(
			attribution, resolve_pronouns)


	def get_all_attribution_html(self, resolve_pronouns=False):
		serializer = AttributionHtmlSerializer()
		return serializer.serialize_attributions(
			self.attributions.values(), resolve_pronouns)


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
		new_attribution = Attribution(self, {
			'id':attribution_id, 'cue':[], 'content':[], 'source':[]
		})

		print new_attribution['id']

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
		self.attributions = OrderedDict()
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
					new_attribution = Attribution(self, {
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






