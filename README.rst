.. corenlp-xml-reader documentation master file, created by
   sphinx-quickstart on Wed Jul  6 22:46:00 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Parc-reader documentation
================================

.. py:module:: corenlp_xml_reader

Purpose
-------

The ``parc_reader`` provides an API in python that simplifies working with
the annotated files in PARC3, while also incorporating parallel annotations
from CoreNLP (if available).

PARC3 consists of files that have been annotated for attribution relations,
each typically consisting of three spans of tokens: a source span (the 
speaker), a content span (what is being quoted), and a cue span (usually
a verb phrase, indicating the act of speech or expression).

When loaded into a ParcCorenlpReader or ParcAnnotatedText object, the
parc consist of sentences containing tokens and attributions whose
properties can be accessed as if they were simple python lists and dicts.

Install
-------

Basic install: ``pip install parc-reader``

Hackable install: 

.. code-block:: bash

   git clone https://github.com/enewe101/parc-reader.git
   cd parc-reader
   python setup.py develop


``ParcCorenlpReader`` vs. ``ParcAnnotatedText``
-----------------------------------------------

If you just want to work with PARC3 files (and you don't have parallel
CoreNLP annotations), then you will want to use the ``ParcAnnotatedText``
class.  It exposes the API for working with PARC-only data.

If you also have parallel CoreNLP annotations, and you want to be able
to access both information from PARC and CoreNLP annotations, then you
want to use ``ParcCorenlpReader``.


``ParcCorenlpReader`` Examples
------------------------------

Instances of ``ParcCorenlpReader`` monkey-patch contents of the 
corresponding ``CorenlpAnnotatedText`` object built from the parallel
CoreNLP annotation of a PARC article. So the 
``ParcCorenlpReader`` feels just like a ``CorenlpAnnotatedText`` that has 
been augmented with PARC annotations.

Before continuing, be familiar with the `API
<https://github.com/enewe101/corenlp-xml-reader.git>`_
for ``CorenlpAnnotatedText`` objects, all of which is satisfied by the 
``ParcCorenlpReader``.

To begin working with PARC / CoreNLP data, make an instance of the ``ParcCorenlpReader``.  You'll need to supply its constructor with three strings representing the parc xml, corenlp xml, and also the raw article text (which has paragraph break information in it):

.. code-block:: python

    >>> from parc_reader import ParcCorenlpReader as P
    >>>
    >>> parc_xml = open('data/example-parc.xml').read()
    >>> corenlp_xml = open('data/example-corenlp.xml').read()
    >>> raw_text = open('data/example-raw.txt').read()
    >>>
    >>> article = P(corenlp_xml, parc_xml, raw_text)

(Note that both the parc_xml and raw_text are optional.  Usually it's 
desired to provide both of them, but if, for example, there is no parc xml
for the data you're loading, you can use this class to *create it*.  More
on that below.)

You can follow along using the same example data which ships with this
git repo.  If you installed using pip, you can just 
`download the example data a-la-carte.
<http://cgi.cs.mcgill.ca/~enewel3/temp/parc/parc-example-data.tgz>`_

The first thing to notice is that, in addition to having a sentences list
the reader also creates a list of paragraphs.  Each paragraph is itself,
unsurprisingly, a list of sentences.  Sentences know what paragraph they're
in too.

.. code-block:: python

    >>> type(article.paragraph)
    <type 'list'>
    >>> print 'this article has %d pragraphs' % len(article.paragraphs)
    this article has 17 pragraphs
    >>>
    >>> second_paragraph = article.paragraphs[1]
    >>> first_sent_second_para = second_paragraph[0]
    >>> print ' '.join([
    ...     token['word'] for token in first_sent_second_para['tokens']
    ... ])
    Not only is development of the new company 's initial machine tied directly to Mr. Cray , so is its balance sheet .
    >>> first_sent_second_para['paragraph_idx']
    1

Sentences accessed this way (or by indexing into the ``article.sentences``
list) have all of the usual features that they do in the 
``corenlp_xml_reader``, plus ``attributions``.  A sentence's attributions 
property is a dictionary
of attribution objects, with the keys being the PARC3 attribution
relation ids.  Let's have a look at the second sentence of the second 
paragraph, which has an attribution in it:

.. code-block:: python

    >>> sentence = second_paragraph[1]
    >>> sentence.keys()
    ['tokens', 'entities', 'attributions', 'references', 'mentions', 'root', 'id', 'paragraph_idx']
    >>> len(sentence['attributions'])
    ... 1

Attributions have as properties an ``'id'``, as well as ``'source'``, 
``'cue'``, and ``'content'`` spans:

.. code-block:: python

    >>> attribution = sentence['attributions'].values()[0]
    >>> attribution.keys()
    ['content', 'source', 'cue', 'id']
    >>>
    >>> print attribution['id']
    wsj_0018_PDTB_annotation_level.xml_set_0

The text spans in attributions are just lists of tokens -- the same kind
of token as is found in ``corenlp_xml_reader``.  Be warned that, while
every attribution is guaranteed to have a non-empty ``'cue'``, the 
``'source'`` is sometimes empty.  One additional feature that tokens have,
beyond those of ``corenlp_xml_reader`` is that they know if they are in an 
attribution, and they know what role (which span) they are part of, and 
retain a reference back to the attribution itself.  So it is possible 
both to get all the tokens in a given attribution span, as well as to check
if a given token is part of an attribution.

.. code-block:: python

    >>> source_tokens = attribution['source']
    >>> print ' '.join([token['word'] for token in source_tokens])
    Documents filed with the Securities and Exchange Commission on the pending spinoff
    >>>
    >>> securities = source_tokens[4]
    >>> securities.keys()
    ['attribution', 'word', 'character_offset_begin', 'character_offset_end', 'pos', 'children', 'lemma', 'sentence_id', 'entity_idx', 'speaker', 'mention', 'parents', 'role', 'ner', 'id']
    >>> print securities['role']
    source
    >>> attribution == securities['attribution']
    True

Careful not to confuse the token property ``'speaker'`` which is inherited
from CoreNLP and is not related to the ``'source'`` of attributions!
It's best to ignore ``'speaker'``!

There is also a global attributions dict if you just want to iterate over
all attributions in the file.

.. code-block:: python

    >>> len(article.attributions)
    18
    >>> print '\n'.join(article.attributions.keys())
    wsj_0018_PDTB_annotation_level.xml_set_5
    wsj_0018_Attribution_relation_level.xml_set_3
    wsj_0018_PDTB_annotation_level.xml_set_7
    wsj_0018_PDTB_annotation_level.xml_set_6
    wsj_0018_Attribution_relation_level.xml_set_6
    wsj_0018_PDTB_annotation_level.xml_set_0
    wsj_0018_PDTB_annotation_level.xml_set_3
    wsj_0018_PDTB_annotation_level.xml_set_2
    wsj_0018_Attribution_relation_level.xml_set_8
    wsj_0018_Attribution_relation_level.xml_set_5
    wsj_0018_PDTB_annotation_level.xml_set_8
    wsj_0018_Attribution_relation_level.xml_set_2
    wsj_0018_Attribution_relation_level.xml_set_1
    wsj_0018_Attribution_relation_level.xml_set_4
    wsj_0018_Nested_relation_level.xml_set_10
    wsj_0018_PDTB_annotation_level.xml_set_1
    wsj_0018_Attribution_relation_level.xml_set_9
    wsj_0018_Attribution_relation_level.xml_set_7

Prounoun interpolation in attributions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Oftentimes a source will contain a pronoun, like "he", "she", or "they".
These can be automatically substituted with a more informative sequence of
tokens found using CoreNLPs coreference resolution:

.. code-block:: python

    >>> article.attributions['some-attribution-id'].interpolate_source_pronouns()

Doing this will find the "representative" mention corresponding to any pronouns
in the attribution's source, and will use it to replace the pronouns.  It will
have a few effects, aside from just replacing the pronouns in the attribution's
``'source'`` token list. It also replaces the pronouns in the sentence's token
list, and it grafts the replacement into the dependency tree as well.  So this
brings about a relatively full substitution.

One important side effect, though, is that the token ``'id'``\ s in the
interpolated sentence will no longer be consecutive, nor unique.


Creating New Attributions
-------------------------
As mentioned above, it is possible to create a ``ParcCorenlpReader`` without
loading any parc_xml (if for example if none exists for the given article). 
This can be useful if you want to programatically *add* annotation 
information to existing CoreNLP annotations.  To do that, simply create
a ``ParcCorenlpReader`` instance without supplying anything for the parc_xml
argument.  

You can also add additional annotations even if you've loaded parc_xml.  
Just make a ``ParcCorenlpReader`` as usual, and use the commands shown 
below.

To make a new annotation, use the function ``add_annotation``.  Supply the 
source, cue, and content token lists as parameters.  The tokens supplied 
should be actual tokens from the article itself.  Suppose we have the following sentence, and we want to mark the attribution that occurs in it:

.. code-block:: python

    >>> article.sentence[0]
        Sentence 0:
             0: Pierre (0,6) NNP PERSON
             1: Vinken (7,13) NNP PERSON
             2: , (14,15) , -
             3: 61 (16,18) CD DURATION
             4: years (19,24) NNS DURATION
             5: old (25,28) JJ DURATION
             6: , (29,30) , -
             7: said (31,35) VB -
             8: he (36,38) PRP -
             9: will (31,35) MD -
            10: join (36,40) VB -
            11: the (41,44) DT -
            12: board (45,50) NN -
            14: as (51,53) IN -
            15: a (54,55) DT -
            16: nonexecutive (56,68) JJ -
            17: director (69,77) NN -
            18: Nov. (78,82) NNP DATE
            19: 29 (83,85) CD DATE
            20: . (86,87) . -

We collect the tokens involved in different parts of the attribution, and
use them to create a new attribution:

.. code-block:: python

    >>> source = article.sentences[0]['tokens'][0:2]
    >>> cue = article.sentences[0]['tokens'][7:8]
    >>> content = article.sentences[0]['tokens'][8:20]
    >>> 
    >>> attribution = article.add_attribution(
        cue_tokens=cue, 
        content_tokens=content, 
        source_tokens=source, 
        id_formatter='my_attribution_'
    )

References to the new attribution will automatically be created in the 
global attributions dictionary, in the sentence(s) involved, and in the 
tokens involved in the attribution.  
It also adds role information to the tokens.  In other words, the result is 
exactly as if the attribution were read from a parc_xml file:

.. code-block:: python

    >>> article.attributions.keys()
    'my_attribution_0'
    >>> article.sentences[0]['attributions'].keys()
    'my_attribution_0'
    >>>
    >>> article.sentences[0]['tokens'][0]['role']
    'source'
    >>>
    >>> article.sentences[0]['tokens'][0]['attribution']
    {'my_attribution_0': {
        'id': 'my_attribution_0',
        'source': [ 
             0: Pierre (0,6) NNP PERSON,
             1: Vinken (7,13) NNP PERSON],
        'cue': [7: said (31,35) VB -],
        'content': [
             8: he (36,38) PRP -,
             9: will (31,35) MD -,
            10: join (36,40) VB -,
            11: the (41,44) DT -,
            12: board (45,50) NN -,
            14: as (51,53) IN -,
            15: a (54,55) DT -,
            16: nonexecutive (56,68) JJ -,
            17: director (69,77) NN -,
            18: Nov. (78,82) NNP DATE,
            19: 29 (83,85) CD DATE]
        }
    }

The call signature for ``add_attribution`` is:

.. code-block:: python

	add_attribution(
		cue_tokens=[], 
		content_tokens=[], 
		source_tokens=[], 
		attribution_id=None,
		id_formatter=''
	)

All of the arguments to ``add_attribution`` are optional, meaning that you can 
create an empty attribution and fill it later  
(described below).  Every attribution must be given a unique id.  You can either
supply the id via the ``attribution_id`` parameter, or you can simply supply
an ``id_formatter`` which is a prefix that gets an incrementing integer added
onto it to create a unique id.  If the ``id_formatter`` contains a ``'%d'`` then
this will be replaced by the integer so you can have arbitrarily formatted ids.
If you supply neither an ``attribution_id`` nor an ``id_formatter``, then the id 
will simply be an integer (as a string).

You can also make an empty attribution, and then fill in tokens for given roles 
afterwards.  The following has the exact same effect as the previous example:

.. code-block:: python

    >>> source = article.sentences[0]['tokens'][0:2]
    >>> cue = article.sentences[0]['tokens'][7:8]
    >>> content = article.sentences[0]['tokens'][8:20]
    >>> 
    >>> attribution = article.add_attribution(id_formatter='my\_attribution\_')
    >>>
    >>> article.add_to_attribution(attribution, 'source', source)
    >>> article.add_to_attribution(attribution, 'cue', cue)
    >>> article.add_to_attribution(attribution, 'content', content)

Note that it isn't necessary to supply tokens for each role.  For example
you could just supply token(s) for the 'cue' role, or indeed leave the 
attribution completely empty.

Note that tokens can only be part of one attribution.  The ``ParcCorenlpReader``
doesn't support nested or overlapping attributions!

Trying to create an attribution using an attribution_id that's already in use,
or trying to create an attribution involving token(s) that are already part
of another attribution will cause a ``ValueError`` to be raised.

Finally, you can delete attributions by supplying the `attribution_id`.
All references throughout the datastructure to the attribution will be
cleaned up.

.. code-block:: python

    >>> 'my_attribution_0' in article.attributions
    True
    >>>
    >>> article.remove_attribution('my_attribution_0')
    >>>
    >>> 'my_attribution_0' in article.attributions
    False


Saving Parc Files to Disk
---------------------------

You can obtain an xml serialization of a ParcCorenlpReader, in the 
xml format used by the parc3 dataset, then save it to disk, as follows:

.. code-block:: python

    >>> xml_string = article.get_parc_xml(indent='  ')
    >>> open('my-parc-file.xml', 'w').write(xml_string)

