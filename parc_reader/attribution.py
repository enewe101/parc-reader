from corenlp_xml_reader import Token

class Attribution(dict):

	def __init__(self, parc_corenlp_document, *args, **kwargs): 
		# This class is basically a dictionary, but it keeps a special
		# Reference, as an attribute, to the document in which the textual
		# attribution arises.
		super(Attribution, self).__init__(*args, **kwargs)
		self.document = parc_corenlp_document


	def get_sentence_ids(self):
		all_span_tokens = self['cue'] + self['source'] + self['content']
		sentence_ids = {t['sentence_id'] for t in all_span_tokens}
		return sentence_ids


	def interpolate_source_pronouns(self):

		new_source = []
		for token in self['source']:

			# If the token is not a preposition, copy it over unchanged 
			if token['pos'] != 'PRP':
				new_source.append(token)
				continue

			# Try to find substitution tokens to replace the pronoun.
			# If none are found, then simply copy over the token unchanged.
			substitute_tokens = self.get_token_substitution(token)
			if substitute_tokens is None:
				new_source.append(token)

			# If we did find a replacement, then put it in place of the
			# original.  Graft it into the source sequence, sentence sequence,
			# and dependency tree structure
			else:

				new_source.extend(substitute_tokens)

				# the replacement tokens subtree in place of the original token
				# in the dependency parse
				head_substitute = self.document._find_head(
					substitute_tokens)[0] or substitute_tokens[0]
				graft_to_dependency_tree(token, head_substitute)

				# Replace the token in the sentence token sequence.
				sentence = self.document.sentences[token['sentence_id']]
				token_idx = sentence['tokens'].index(token)
				sentence['tokens'] = (
					sentence['tokens'][:token_idx]
					+ substitute_tokens
					+ sentence['tokens'][token_idx+1:]
				)

				# Now alter the substitute tokens to make them seem like they
				# really came from this sentence
				for sub_token in substitute_tokens:
					sub_token['sentence_id'] = token['sentence_id']
					sub_token['attribution'] = self
					sub_token['role'] = 'source'

		self['source'] = new_source


	def get_token_substitution(self, token):

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

		# Now we want to clone each of the tokens from the representative
		# mention, and graft them into the sentence, replacing the old token.
		# We want to stitch the replacement into the linear sequence of tokens,
		# into the dependency tree, and into the constituency parse.
		substitute_tokens = clone_tree(representative['tokens'])

		# Finally, capitalize the first token in the substitution if it
		# replaces the first token in the sentence.
		if token['id'] == 0:
			capitalized = Token(substitute_tokens[0])
			capitalized['word'] = capitalized['word'].capitalize()
			substitute_tokens = [capitalized] + substitute_tokens[1:]

		return substitute_tokens


	def __eq__(self, other):
		"""
		See the docstring for corenlp_xml_reader.Sentence.__eq__().
		"""
		return id(self) == id(other)


	def __ne__(self, other):
		return not self.__eq__(other)


def graft_to_dependency_tree(token, substitute_token):
	"""
	Remove token from the its place in the its dependency tree, and replace it
	by substitute token.  Dependency links are two-way (the parent has a
	pointer to the child, and the child to the parent).  So grafting involves
	adding pointers from original token's neighbors to to the substitute, in 
	addition to adding pointers from the substitute to the original token's 
	neighbors.
	"""

	# Graft the substitute tokens by replacing the links to the token being
	# replace with links to the substitute token
	for relation, child_token in token['children']:

		# Copy the link that the original's children links onto the substitute
		# token
		substitute_token['children'].append((relation, child_token))

		# Make the original's children point to the substitute
		new_child_parents = []
		for relation, parent_token in child_token['parents']:

			# If this is the link to the token being replaced, then make it
			# link to the substitute now. Otherwise copy it over as-is
			if parent_token['id'] == token['id']:
				new_child_parents.append((relation, substitute_token))
			else:
				new_child_parents.append((relation, parent_token))

		child_token['parents'] = new_child_parents

	# Now copy the original's links to its parents over to the substitute
	for relation, parent_token in token['parents']:

		substitute_token['parents'].append((relation, parent_token))

		# Make the original's parents point to the substitute
		new_parent_children = []
		for relation, child_token in parent_token['children']:

			# if this is a link to the original token, make it point to the
			# substitute.  Otherwise copy it over as-is
			if child_token['id'] == token['id']:
				new_parent_children.append((relation, substitute_token))
			else:
				new_parent_children.append((relation, child_token))

		parent_token['children'] = new_parent_children



# NOTE: clone_tree clones the provided tokens, reproducing the internal
# structure of dependency tree links (while discaring links leading outside of
# the tokens provided).  However, no attempt is made to clone the portion of
# the constituency tree that these tokens are involved in.
def clone_tree(tokens):
	# first, clone each token individually, and keep a link between the original
	# and the cloned version
	clone_lookup = {}
	for token in tokens:
		clone = Token(token)
		#clone['word'] = 'clone-' + clone['word'] # debug: keep track of clone
		clone_lookup[token['id']] = clone

	# Now we go through the dependency tree structure, and make all pointers in
	# the clones point to their clone peers instead of back to the original
	# tokens

	# Currently for dependency links that were internal to this group of tokens
	# the corresponding links on the clones still point back to the original
	# tokens.  Make them point to the corresponding clone
	for token in clone_lookup.values():

		# Re-map links to parents
		new_parents = []
		for relation, parent_token in token['parents']:
			if parent_token['id'] in clone_lookup:
				new_parents.append((
					relation, clone_lookup[parent_token['id']]))
		token['parents'] = new_parents

		# Re-map links to children
		new_children = []
		for relation, child_token in token['children']:
			if child_token['id'] in clone_lookup:
				new_children.append((
					relation, clone_lookup[child_token['id']]))
		token['children'] = new_children

	# Return the clones in the sequence given by their corresponding originals
	return [clone_lookup[token['id']] for token in tokens]

