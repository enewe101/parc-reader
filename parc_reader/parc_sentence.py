from parc_reader.utils import get_spans


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





