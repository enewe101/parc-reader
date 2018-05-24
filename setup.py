'''
Setup for the parc-reader, a utility for reading the PARC3 dataset and
parallel CoreNLP annotations, designed to make working with the PARC3 
dataset easy in Python.
'''

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'parc_reader/README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='parc-reader',

    # Versions should comply with PEP440.  For a discussion on 
	# single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.1.5',

    description='Work with the PARC dataset in Python',
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/enewe101/parc-reader',

    # Author details
    author='Edward Newell',
    author_email='edward.newell@gmail.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here.
        'Programming Language :: Python :: 2.7',
    ],

    # What does your project relate to?
    keywords= (
		'NLP natrual language processing computational linguistics '
		'Penn Attribution Relation Corpus PARC PARC3'
	),

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=['parc_reader'],
	#indlude_package_data=True,
	package_data={'': [
		'README.md',
		'data/example-raw.txt',
		'data/example-parc.xml',
		'data/example-corenlp.xml',
	]},
	install_requires=['bs4', 'corenlp-xml-reader>=0.1.2', 'brat-reader']
)
