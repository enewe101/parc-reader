import parc_reader
import t4k
import re
import os
import subprocess
import SETTINGS
import json
import random

MAX_ARTICLE_NUM = 2499
ARTICLE_NUM_MATCHER = re.compile('wsj_(\d\d\d\d)')


def get_article_num(article_fname):
    return int(ARTICLE_NUM_MATCHER.search(article_fname).group(1))


def get_parc_fname(doc_num):
    return 'wsj_%s' % str(doc_num).zfill(4)


def get_raw_path(doc_num):
    fname = get_parc_fname(doc_num)

    # Determine the subdir by getting the hundreds from the doc_num
    prefix_digits = doc_num / 100
    if prefix_digits < 23:
        raw_dir = SETTINGS.RAW_TRAIN_DIR
    elif prefix_digits < 24:
        raw_dir = SETTINGS.RAW_TEST_DIR
    elif prefix_digits < 25:
        raw_dir = SETTINGS.RAW_DEV_DIR
    else:
        raise ValueError(
            "Parc data has no articles with ids in the range of %d00's."
            % prefix_digits
        )
    subsubdir = str(prefix_digits).zfill(2)

    return os.path.join(raw_dir, fname)


def raw_article_exists(doc_num):
    try:
        open(get_raw_path(doc_num))
    except IOError:
        return False
    return True


def corenlp_article_exists(doc_num):
    try:
        open(get_corenlp_path(doc_num))
    except IOError:
        return False
    return True


def get_corenlp_path(doc_num):
    fname = get_parc_fname(doc_num)

    # Determine the subdir by getting the hundreds from the doc_num
    prefix_digits = doc_num / 100
    if prefix_digits < 23:
        corenlp_dir = SETTINGS.CORENLP_TRAIN_DIR
    elif prefix_digits < 24:
        corenlp_dir = SETTINGS.CORENLP_TEST_DIR
    elif prefix_digits < 25:
        corenlp_dir = SETTINGS.CORENLP_DEV_DIR
    else:
        raise ValueError(
            "Parc data has no articles with ids in the range of %d00's."
            % prefix_digits
        )
    subsubdir = str(prefix_digits).zfill(2)

    return os.path.join(corenlp_dir, fname + '.xml')


def get_parc_path(doc_num):

    # Get the actual filename based on the article number
    fname = get_parc_fname(doc_num)

    # Determine the subdir by getting the hundreds from the doc_num
    prefix_digits = doc_num / 100
    if prefix_digits < 23:
        parc_dir = SETTINGS.PARC_TRAIN_DIR
    elif prefix_digits < 24:
        parc_dir = SETTINGS.PARC_TEST_DIR
    elif prefix_digits < 25:
        parc_dir = SETTINGS.PARC_DEV_DIR
    else:
        raise ValueError(
            "Parc data has no articles with ids in the range of %d00's."
            % prefix_digits
        )
    subsubdir = str(prefix_digits).zfill(2)

    return os.path.join(parc_dir, subsubdir, fname + '.xml')


def load_parc_doc(doc_num, include_nested=True):
    """
    Loads a parc file into memory, but does not load the associated corenlp 
    annotations
    """
    return parc_reader.new_parc_annotated_text.read_parc_file(
        open(get_parc_path(doc_num)).read(), doc_num, include_nested
    )



def load_article(doc_num):

    parc_xml = open(get_parc_path(doc_num)).read()
    corenlp_xml = open(get_corenlp_path(doc_num)).read()
    raw_txt = open(get_raw_path(doc_num)).read()

    return parc_reader.new_reader.ParcCorenlpReader(
        corenlp_xml, parc_xml, raw_txt)


def iter_doc_num(subset='train', skip=None, limit=None):
    """
    Provides iteration over named ranges of documents.  The iterator yields the
    document IDs only, not the documents themselves.  Allows you to
    individually select the training, testing, or development subsets, or to
    select all document numbers.
    """
    if subset == 'train':
        start = 0; stop = 2300
    elif subset == 'dev':
        start = 2400; stop = 2500
    elif subset == 'test':
        start = 2300; stop = 2400
    elif subset == 'all':
        start = 0; stop = 2500

    if skip is not None:
        start = max(skip, start)

    if limit is not None:
        stop = min(limit, stop)

    for doc_num in range(start, stop):
        yield doc_num


def iter_parc_docs(subset='train', skip=None, limit=None, include_nested=True):
    """
    Yields all parc files, parsed to surface tokenization, sentence splitting, 
    constituence parse structure, and attributions.
    Specify a subset of the dataset; can be:

        'train', 'test', 'dev', or 'all.

    """
    for doc_num in iter_doc_num(subset, skip=skip, limit=limit):
        doc = try_do(load_parc_doc, doc_num, include_nested)
        if doc is not None:
            yield doc_num, doc


def read_all_parc_files(subset='train', skip=None, limit=None):
    print 'Reading PARC3 files.  This will take a minute...'
    return {
        doc_num : doc
        for doc_num, doc in iter_parc_docs(subset, skip=skip, limit=limit)
    }


def iter_articles(subset='train'):
    """
    Generator that yields all articles in the dataset, according to the subset
    specified.  ``subset`` can be ``'train'``, ``'test'``, ``'dev'``, or
    ``'all'``.
    """
    for doc_num in iter_doc_num(subset):
        doc = try_do(load_article, doc_num)
        if doc is not None:
            yield get_parc_fname(doc_num), doc


def try_do(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (IOError, ValueError):
        return None


def load_corpus_stats():
    corpus_stats_path = os.path.join(
        SETTINGS.DATA_DIR, 'corpus-statistics.json')
    return json.loads(open(corpus_stats_path).read())


def show_attributions(attribution_ids, limit=None):

    # Open a file at which to write results
    out_path = os.path.join(SETTINGS.DATA_DIR, 'view-attrs.html')
    out_f = open(out_path, 'w')

    # Tolerate passing in a single attribution id (normally expect a list).
    if isinstance(attribution_ids, basestring):
        attribution_ids = [attribution_ids]

    # Subsample the attribution_ids keeping at most limit, if desired
    if limit is not None:
        if len(attribution_ids) > limit:
            attribution_ids = set(random.sample(attribution_ids, limit))

    # Get the set of articles (by article number) containing the attributions
    article_nums = set([get_article_num(att_id) for att_id in attribution_ids])

    print '%d articles to load...' % len(article_nums)

    # Load the articles that contain the desired attributions
    articles = {}
    for doc_num in article_nums:
        print 'loading article %d' % doc_num
        articles[doc_num] = load_article(doc_num)

    # Get the real attribution objects for the desired attributions
    attributions = [
        articles[get_article_num(attr_id)].attributions[attr_id]
        for attr_id in attribution_ids
    ]

    # Now we make the HTML
    styling = {
        '.one-attribution': {
            'border': 'solid 2px rgb(220,220,220)',
            'border-radius': '6px',
            'max-width': '800px',
            'margin': 'auto',
            'margin-top': '20px',
            'padding': '14px'
        }
    }
    serializer = (
        parc_reader.attribution_html_serializer.AttributionHtmlSerializer())
    dom, body = serializer.prepare_dom(styling)
    for attribution in attributions:
        attribution_wrapper = body.appendChild(
            t4k.html.div({'class':'one-attribution'}))
        attribution_id = attribution_wrapper.appendChild(
            t4k.html.div({'class':'attribution-id'}))
        attribution_id.appendChild(t4k.html.text(attribution['id']))
        attribution_wrapper.appendChild(
            serializer.get_attribution_element(attribution))

    html = dom.toprettyxml(indent='  ')
    out_f.write(html)

    subprocess.check_output(['open', out_path])


def safe_append(dictionary, key, val):
    '''
    Simulates defaultdict behavior where the default is an empty list
    '''
    try:
        dictionary[key].append(val)
    except KeyError:
        dictionary[key] = [val]


class ParcDataset(object):

    def __init__(
        self, 
        load=None, 
        start=1, 
        limit=MAX_ARTICLE_NUM,
        article_nums=None,
        num_attributions=None,
    ):

        if load is not None:
            self.load(load)
        else:
            self.build(start, limit, article_nums, num_attributions)


    def build(
        self,
        start=1,
        limit=MAX_ARTICLE_NUM,
        article_nums=None,
        num_attributions=None,
    ):
        '''
        Read and build the Parc Dataset.  Default behavior is to build
        all articles, numbered 1 through MAX_ARTICLE_NUM.  There
        are various ways to limit the number of articles that are loaded.
            (1) define start and limit, so that articles numbered
                range(start, limit) will be loaded
            (2) define a specific set of article_nums to be loaded
            (3) define a target num_attributions -- in which case
                articles will be loaded until this number of attributions
                is reached
            * Notes: 
                - method (1) and (2) are not compatible.  Setting 
                    article_nums will override start, limit settings
                - method (3) can be used in conjunction with methods (1)
                    or (2).  Article loading will stop when either all
                    articles nums are loaded, or when the target number of 
                    attributions is reached -- whichever comes first.
            
        articles by defining start and limit.  Or provide an iterable
        of article_nums, in which case start and limit are ignored.
        '''

        self.articles = {}
        self.cues = {}
        self.contents = {}
        self.sources = {}
        self._attributions = {}

        # Pack all data into a tuple for easy saving and loading
        self.data = self.articles, self.cues, self.contents, self.sources

        if article_nums is None:
            article_nums = range(start, limit)
        else:
            article_nums = list(article_nums)

        for doc_num in article_nums:

            # If applicable, check target num_attributions was reached
            if num_attributions is not None:
                if len(self._attributions) >= num_attributions:
                    break

            fname = 'wsj_%s' % str(doc_num).zfill(4)
            print 'reading %s...' % fname

            # Load each article, but tolerate missing files.  There are
            # frequently holes in the file name series.
            try:
                article = load_article(doc_num)
            except IOError:
                continue

            self.articles[doc_num] = article

            for sentence in article.sentences:

                for attribution_id in sentence['attributions']:

                    attribution = sentence['attributions'][attribution_id]
                    back_pointer = {
                        'doc_num': doc_num, 
                        'attribution_id': attribution_id
                    }

                    if attribution_id in self._attributions:
                        continue
                    
                    self._attributions[attribution_id] = back_pointer

                    cue = ' '.join([t['word'] for t in attribution['cue']])
                    safe_append(self.cues, cue, back_pointer)

                    source = ' '.join([
                        t['word'] for t in attribution['source']])
                    safe_append(self.sources, source, back_pointer)

                    content = ' '.join([
                        t['word'] for t in attribution['content']])
                    safe_append(self.contents, content, back_pointer)


    def print_cue_grep(self, pattern):
        matcher = re.compile(pattern)
        for cue in self.cues:
            if matcher.search(cue):
                print cue.upper()
                for example in self.cues[cue]:
                    attribution_id = example['attribution_id']
                    print attribution_id
                    article = self.articles[example['doc_num']]

                    attribution = article.attributions[attribution_id]
                    sentence_ids = attribution.get_sentence_ids()
                    print sentence_ids
                    sentences = article.sentences[
                            min(sentence_ids) : max(sentence_ids) + 1
                    ]
                    tokens = t4k.flatten([s['tokens'] for s in sentences])
                    print '-->\t' + ' '.join(
                        [t['word'] for t in tokens])
                print '\n'


    def source_grep(self, pattern):
        matcher = re.compile(pattern)
        matched_sources = {}
        for source in self.sources:
            if matcher.search(source):
                matched_sources[source] = self.sources[source]

        return matched_sources


    def transform_sentence(self, sentence):

        tokens = []
        for token in sentence['tokens']:
            if token['role'] == 'source' and token['pos'] == 'PRP':
                if len(token['mentions']) > 0:
                    ref = token['mentions'][0]['reference']
                    representative_tokens = ref['representative']['tokens']
                    tokens.extend([
                        t['word']+'('+token['role']+')' 
                        for t in representative_tokens])
                else:
                    tokens.append(
                        token['word']+'('+token['pos']+')'
                        +'('+token['role']+')'
                    )

            else:
                tokens.append(
                    token['word']+'('+token['pos']+')'
                    +'('+str(token['role'])+')'
                )

        return ' '.join(tokens)



    def cue_grep(self, pattern):
        matcher = re.compile(pattern)
        matched_cues = {}
        for cue in self.cues:
            if matcher.search(cue):
                matched_cues[cue] = self.cues[cue]

        return matched_cues


    def cue_grep_html(self, pattern):
        matched = self.cue_grep(pattern)
        for cue in matched:
            print '\n' + cue.upper()
            for attribution_address in matched[cue]:
                print self.get_attribution_html(
                    **attribution_address
                ) + '\n'


    def attributions(self):
        '''
        Generator that yields the fully populated attributions from the
        dataset reader.
        '''
        for attribution_spec in self._attributions:
            article = self.articles[attribution_spec['doc_num']]
            attribution = article.attributions[
                attribution_spec['attribution_id']]
            yield attribution, article


    def get_attribution(self, doc_num, attribution_id):
        return self.articles[doc_num].attributions[attribution_id]


    def get_attribution_html(
        self,
        doc_num,
        attribution_id,
        resolve_pronouns=False
    ):
        '''
        Delegate to the method on the underlying ParcCorenlpReader.
        '''
        article = self.articles[doc_num]
        attribution = article.attributions[attribution_id]
        return article.get_attribution_html(attribution, resolve_pronouns)



if __name__ == '__main__':
    cues = get_all_cues()
    print '\n'.join(cues)
