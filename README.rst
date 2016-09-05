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
CoreNLP annotation of a PARC article.  In this way, the 
``ParcCorenlpReader`` inserts information from the PARC annotations and
feels just like a ``CorenlpAnnotatedText`` that has been augmented with
PARC annotations.

Before continuing, be familiar with the `API
<https://github.com/enewe101/corenlp-xml-reader.git>`_
for ``CorenlpAnnotatedText`` objects, all of which is satisfied by the 
``ParcCorenlpReader``.


