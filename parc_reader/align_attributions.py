import itertools as it
import t4k
import sys
import SETTINGS as SETTINGS
from collections import defaultdict
import parc_reader


class MultiAlignedAttributions(object):
    """
    Given N ParcAnnotatedReader instances, align their attributions so
    that we can score how well they agree.

    This provides access to all of the N*(N-1)/2 comparisons using a uniform
    addressing system: specifically, it makes the comparison between A and B
    available as either A compared to B or B compared to A, which are
    essentially the same, but for which the meaning of precision and recall are
    flipped.
    """

    def __init__(self, parc_reader_objects):
        self.parc_reader_objects = parc_reader_objects
        self.validate()
        combos = it.permutations(range(len(parc_reader_objects)), 2)
        self.aligned = {(i,j): self._align(i,j) for i,j in combos}

    def validate(self):
        if len(self.parc_reader_objects) < 2:
            raise ValueError(
                'you must provide at least two parc reader objects to compare.'
                ' Got %d' % len(parc_reader_objects)
            )

    def __getitem__(self, (i,j)):
        return self.aligned[i,j]

    def _align(self, i, j):
        reader1 = self.parc_reader_objects[i]
        reader2 = self.parc_reader_objects[j]
        return AlignedAttributions(reader1, reader2)


class AlignedAttributions(object):
    """
    Given two ParcAnnotatedReader instances, align their attributions so
    that we can score how well the attributions were extracted.  The 
    first ParcAnnotatedReader instance should contain the gold or reference 
    attributions, and the second should be the extracted attributions.

    Once they are aligned, statistics like precision, recall, and agreement
    can be calculated.
    """

    def __init__(self, parc_reader_reference, parc_reader_extract):
        self.reference = parc_reader_reference
        self.extract = parc_reader_extract
        if not self.ensure_match():
            raise ValueError(
                'The two ParcCorenlpReader instances must contain the '
                'same sentences and tokens.'
            )
        self.align()


    def ensure_match(self):
        """
        Verifies that the two articles are the same token-for-token.
        """
        for s1, s2 in zip(self.reference.sentences, self.extract.sentences):
            for t1, t2 in zip(s1['tokens'], s2['tokens']):
                if t1['word'] != t2['word']:
                    return False
        return True


    def align(self):
        """
        Matches attributions from the reference document to the predicted 
        attribution extracts document.
        """

        # When considering recall, we're interested trying to align each
        # reference attribution to the best (highest recall) predicted 
        # attribution. However, a reference attribution might overlap with 
        # other predicted attributions too, and we'll still cache those.

        self.all_recalls, self.best_recalls = self._align(
            self.reference.attributions, self.extract.attributions)

        self.all_precisions, self.best_precisions = self._align(
            self.extract.attributions, self.reference.attributions)


    def _align(self, expected_attributions, found_attributions):

        # Before attempting to do alignments, make a map from each 
        # attribution to its sentences.
        found_attrs_lookup = AttrSentenceLookup(found_attributions)

        # Find best predicted attribution for each reference attribution.
        all_alignments = defaultdict(dict)
        best_alignments = {}
        for expected_attr_id in expected_attributions:

            # Find eligible extracted attributions that overlap with
            # the same sentences (if any)
            expected_attr = expected_attributions[expected_attr_id]
            exp_sentences = expected_attr.get_sentence_ids()
            eligible_found_attrs = found_attrs_lookup.lookup(exp_sentences)

            # There may be no overlap at all with this attribution...
            if len(eligible_found_attrs) == 0:
                best_alignments[expected_attr_id] = None

            # If there is exactly one eligible predicted attribution, then
            # select it to be the best match.  
            elif len(eligible_found_attrs) == 1:
                found_attr_id = list(eligible_found_attrs)[0]
                found_attr = found_attributions[found_attr_id]
                overlap = attribution_overlap(expected_attr, found_attr)
                best_alignments[expected_attr_id] = (found_attr_id, overlap)
                all_alignments[expected_attr_id][found_attr_id] = overlap

            # If there are many eligible attributions, take the one with 
            # the best overlap score.
            else:
                maxx = t4k.Max()
                for found_attr_id in eligible_found_attrs:
                    found_attr = found_attributions[found_attr_id]
                    overlap = attribution_overlap(expected_attr, found_attr)
                    all_alignments[expected_attr_id][found_attr_id]=overlap
                    maxx.add(overlap['overall'], (found_attr_id, overlap))
                overall, (best_found_attr_id, overlap) = maxx.get()
                best_alignments[expected_attr_id] = (
                    best_found_attr_id, overlap)

        return all_alignments, best_alignments


    def confusion(self, strictness='soft'):
        """
        Provide confusion matrix entries either based on the soft metric
        (tokenwise proportion of overlap) or the strict overlap (binary; 
        either perfect prediction or wrong).

        Having the confusion matrix entries is useful for calculating 
        microaveraged precision, recall, and f1.
        """
        raise NotImplementedError()


    def precision(self, strictness='soft'):
        """
        Provide the precision for attribution extraction given the gold
        (reference) and extracted attributions.  Base the precision either
        on strict (correct only if all tokens predicted correctly) or soft
        (fraction of tokens predicted correctly).
        """
        raise NotImplementedError()


    def attr_precision(self, extracted_attr_id):
        return best_precisions[attr_id]


    def pair_precision(self, extracted_attr_id, reference_attr_id):
        return all_precisions[extracted_attr_id][reference_attr_id]


    def recall(self, strictness='soft'):
        raise NotImplementedError()


    def attr_recall(self, attr_id):
        return best_recalls[attr_id]


    def pair_recall(self, reference_attr_id, extracted_attr_id):
        return all_recalls[reference_attr_id, extracted_attr_id]




def attribution_overlap(attr1, attr2):
    """
    Calculate the token soft token overlap of two attributions, and 
    determine if the attributions match perfectly.  Return the result
    as a tuple (soft_overlap, perfect_match).

    When attr1 is a gold attribution and attr2 is a predicted attribution, 
    this is equivalent to the soft and strict recall.  When roles are 
    reversed, it is equivalent to the soft and strict precision.
    """

    overall_denominator = 0
    overall_numerator = 0
    perfect_match = True
    role_overlaps = {}
    for role in SETTINGS.ROLES:

        # It's easier to compare tokens by comparing their signatures.
        # Get token signatures for tokens in this role for the attributions.
        tokens1 = set([get_token_signature(t) for t in attr1[role]])
        tokens2 = set([get_token_signature(t) for t in attr2[role]])
        intersect = tokens1 & tokens2

        # Check if we've maintained a perfect match.
        different_len = len(tokens1) != len(tokens2)
        missed_token = len(intersect) != len(tokens1)
        if different_len or missed_token:
            perfect_match = False

        # Otherwise, we calculate the token-wise precision or recall.
        overall_denominator += len(tokens1) # true-pos and false-neg
        overall_numerator += len(intersect) # true-pos

        # Calculate component overlap.  First handle division by zero.
        if len(tokens1) == 0:
            role_overlaps[role] = 1.0
        else:
            role_overlaps[role] = len(intersect) / float(len(tokens1))

    # Now calculate the soft overlap. Handle division by zero first.
    # If there is no division by zero, calculate the score normally
    if overall_denominator == 0:
        score = 1.0  # "Recall is perfect if there's nothing to recall"
    else:
        score =  overall_numerator / float(overall_denominator)

    # Return the soft overlap and whether the match is perfect
    return {
        'overall': score, 
        'perfect': perfect_match,
        'cue': role_overlaps['cue'],
        'source': role_overlaps['source'],
        'content': role_overlaps['content']
    }


def get_token_signature(token):
    """
    Returns a 3-tuple that uniquely identifies a token within an article
    """
    return token['sentence_id'], token['word'], token['id']
        


class AttrSentenceLookup(object):
    """
    Allows you to look up the attributions in a given ParcCorenlpReader
    instance that are found within a given set of sentences.
    """

    def __init__(self, attributions_dict):
        """
        Makes a dictionary that maps sentences to the attribution(s) that 
        occur within them.
        """
        self.lookup_dict = defaultdict(set)
        for attr_id in attributions_dict:
            attr = attributions_dict[attr_id]
            for sentence_id in attr.get_sentence_ids():
                self.lookup_dict[sentence_id].add(attr_id)


    def lookup(self, sentence_ids):
        """
        Find all attributions that overlap with the given sentence ids.
        """
        if isinstance(sentence_ids, int):
            sentence_ids = [sentence_ids]

        found_attributions = set()
        for sentence_id in sentence_ids:
            found_attributions |= self.lookup_dict[sentence_id]

        return found_attributions

