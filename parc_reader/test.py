from unittest import main, TestCase
from parc_reader.new_reader import ParcCorenlpReader

def get_test_texts():
    return (
        open('data/example-corenlp.xml').read(),
        open('data/example-parc.xml').read(),
        open('data/example-raw.txt').read()
    )

def get_test_article():
    return ParcCorenlpReader(*get_test_texts())


class TestReader(TestCase):

    def test_reader(self):
        article = get_test_article()

        # Test structure of specific attributions, and that there are the 
        # correct number of attributions

        # Test a case where attributions or spans overlap


if __name__ == '__main__':
    main()
