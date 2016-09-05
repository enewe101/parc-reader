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
    >>> raw_text = oepn('data/example-raw.txt').read()
    >>>
    >>> article = P(parc_xml, corenlp_xml, raw_text)

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
    Not only is development of the new company 's initial machine tied 
    directly to Mr. Cray , so is its balance sheet .
    >>> first_sent_second_para['paragraph_idx']
    1

Sentences accessed this way (or by indexing into the ``article.sentences``
list) have all of the usual features that they do in the corenlp_xml_reader,
plus ``attributions``.  A sentence's attributions property is a dictionary
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
of token as is found in corenlp_xml_reader.  Notice, however, that 
tokens know if they are in an attribution, and they know what role (which
span) they are part of, and retain a reference back to the attribution 
itself.

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
    >>> print article.attributions.keys()
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
