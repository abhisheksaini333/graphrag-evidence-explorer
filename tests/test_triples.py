import json
import unittest
from explorer.triples import parse_triples
from explorer.domain import Invalid


class TripleTests(unittest.TestCase):
    def test_supported_triples_keep_the_exact_support_span(self):
        text='Mira owns Atlas. Atlas depends on Boreal.'
        raw=json.dumps([{'subject':'Mira','relation':'owns','object':'Atlas'},{'subject':'Atlas','relation':'depends','object':'Boreal'}])
        result=parse_triples(raw,text)
        self.assertEqual(len(result['accepted']),2)
        for claim in result['accepted']:
            self.assertEqual(claim['support'],text[claim['start']:claim['end']])
        self.assertEqual(result['rejected'],[])

    def test_wrong_predicate_assignment_is_rejected_even_when_words_exist_elsewhere(self):
        text='Boreal uses the Cedar database. Nora maintains Cedar.'
        raw=json.dumps([{'subject':'Boreal','relation':'maintains','object':'Cedar'},{'subject':'Nora','relation':'maintains','object':'Cedar'}])
        result=parse_triples(raw,text)
        self.assertEqual([x['subject'] for x in result['accepted']],['Nora'])
        self.assertEqual(len(result['rejected']),1)

    def test_hallucinated_entities_and_graph_delimiters_are_not_accepted(self):
        raw=json.dumps([{'subject':'Omar','relation':'owns','object':'Atlas'},{'subject':'Mira<|>root','relation':'owns','object':'Atlas'}])
        self.assertEqual(parse_triples(raw,'Mira owns Atlas.')['accepted'],[])
        for value in ['not json','{}',json.dumps([{'subject':5}])]:
            with self.assertRaises(Invalid):parse_triples(value,'Mira owns Atlas.')

    def test_duplicate_triples_do_not_inflate_evidence(self):
        item={'subject':'Mira','relation':'owns','object':'Atlas'}
        self.assertEqual(len(parse_triples(json.dumps([item,item]),'Mira owns Atlas.')['accepted']),1)
