from collections import defaultdict
class BratAnnotation(object):

    def __init__(self, brat_text):
        self.parse_brat_text(brat_text)


    def parse_brat_text(self, brat_text):

        self.attributions = {}
        self.spans = {}
        self.attributions_by_span = defaultdict(list)
        self.spans_by_attribution = defaultdict(dict)

        for line in brat_text.split('\n'):
            try:
                if line == '': continue
                label, spec = line.split('\t', 1)
                if label.startswith('E'):
                    self.parse_attribution(label, spec)
                elif label.startswith('T'):
                    self.parse_span(label, spec)
            except Exception:
                print line
                raise

        self.convert_span_identifiers_to_range_spec()

    


    def parse_attribution(self, attr_label, spec):
        self.attributions[attr_label] = {}
        for span_spec in spec.split():
            span_role, span_label = span_spec.split(':')
            if 'Attribution' in span_role:
                continue
            span_role = span_role.lower()
            self.attributions_by_span[span_label].append(attr_label)
            self.spans_by_attribution[attr_label][span_role] = span_label


    def parse_span(self, label, spec):
        role_and_range_specs = spec.split('\t')[0]
        role, range_specs = role_and_range_specs.split(' ', 1)
        ranges = [
            tuple([int(i) for i in r.split(' ')]) 
            for r in range_specs.split(';')
        ]
        self.spans[label] = {'ranges':ranges, 'role':role.lower()}


    def convert_span_identifiers_to_range_spec(self):
        self.attributions = {
            label: {
                key: self.spans[attr_spec[key]]['ranges']
                for key in attr_spec
            }
            for label, attr_spec in self.spans_by_attribution.iteritems()
        }
