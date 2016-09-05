'''
This module contains a couple utility classes used by the ParcCorenlpReader,
and ParcAnnotatedText.
'''

def rangify(iterable):
	'''
	Converts a list of indices into a list of ranges (compatible with the
	range function).  E.g. [1,2,3,7,8,9] becomes [(1,4),(7,10)].
	The iterable provided must be sorted. Duplicate indices are ignored.  
	'''
	ranges = []
	last_idx = None
	for idx in iterable:

		if last_idx is None:
			start = idx

		elif idx - last_idx > 1:
			ranges.append((start, last_idx + 1))
			start = idx

		last_idx = idx

	if last_idx is not None:
		type(ranges)
		ranges.append((start, last_idx + 1))

	return ranges



class IncrementingMap(dict):
	'''
	Assigns incrementing integer keys to arbitrary hashable objects, 
	starting from 0.

	After calling `incrementing_map.add(hashable)`, the key for the object 
	can be retrieved using `incrementing_map[hashable]`, or, the object
	can be looked up using its id by doing `incrementing_map.key(key)`.

	Objects that have the same hash are considered identical, and get the
	same key.  Calling `incrementing_map.key(key)` with their key would
	return the first such object added.
	'''

	def add(self, key):
		if key not in self:
			self[key] = self.get_incrementing_id()
			self._get_keys().append(key)


	def get_incrementing_id(self):
		try:
			self._current_id += 1
		except AttributeError:
			self._current_id = 0
		return self._current_id


	def _get_keys(self):
		'''
		This getter is private, and covers the case where self._keys is not 
		yet defined.  The first time it is called, self._keys is initialized
		to be an empty list.
		'''
		try:
			return self._keys
		except AttributeError:
			self._keys = []
			return self._keys


	def key(self, idx):
		return self._get_keys()[idx]


	def keys(self):
		return [k for k in self._get_keys()]

