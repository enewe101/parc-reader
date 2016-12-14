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


