import unittest

from whoosh import fields, index, qparser
from whoosh.filedb.filestore import RamStorage
from whoosh.qparser import QueryParser
from whoosh.query import *


class TestQueries(unittest.TestCase):
    def test_all_terms(self):
        q = QueryParser("a", None).parse(u'hello b:there c:"my friend"')
        ts = set()
        q.all_terms(ts, phrases=False)
        self.assertEqual(sorted(ts), [("a", "hello"), ("b", "there")])
        ts = set()
        q.all_terms(ts, phrases=True)
        self.assertEqual(sorted(ts), [("a", "hello"), ("b", "there"),
                                      ("c", "friend"), ("c", "my")])
    
    def test_existing_terms(self):
        s = fields.Schema(key=fields.ID, value=fields.TEXT)
        st = RamStorage()
        ix = st.create_index(s)
        
        w = ix.writer()
        w.add_document(key=u"a", value=u"alfa bravo charlie delta echo")
        w.add_document(key=u"b", value=u"foxtrot golf hotel india juliet")
        w.commit()
        
        r = ix.reader()
        q = QueryParser("value", None).parse(u'alfa hotel tango "sierra bravo"')
        
        ts = q.existing_terms(r, phrases=False)
        self.assertEqual(sorted(ts), [("value", "alfa"), ("value", "hotel")])
        
        ts = q.existing_terms(r)
        self.assertEqual(sorted(ts), [("value", "alfa"), ("value", "bravo"), ("value", "hotel")])
        
        ts = set()
        q.existing_terms(r, ts, reverse=True)
        self.assertEqual(sorted(ts), [("value", "sierra"), ("value", "tango")])
    
    def test_replace(self):
        q = And([Or([Term("a", "b"), Term("b", "c")], boost=1.2), Variations("a", "b", boost=2.0)])
        q = q.replace("b", "BB")
        self.assertEqual(q, And([Or([Term("a", "BB"), Term("b", "c")], boost=1.2), Variations("a", "BB", boost=2.0)]))
    
    def test_apply(self):
        def visit(q):
            if isinstance(q, (Term, Variations, FuzzyTerm)):
                q.text = q.text.upper()
                return q
            return q.apply(visit)
        
        before = And([Not(Term("a", u"b")), Variations("a", u"c"), Not(FuzzyTerm("a", u"d"))])
        after = visit(before)
        self.assertEqual(after, And([Not(Term("a", u"B")), Variations("a", u"C"), Not(FuzzyTerm("a", u"D"))]))
        
        def term2var(q):
            if isinstance(q, Term):
                return Variations(q.fieldname, q.text)
            else:
                return q.apply(term2var)
    
        q = And([Term("f", "alfa"), Or([Term("f", "bravo"), Not(Term("f", "charlie"))])])
        q = term2var(q)
        self.assertEqual(q, And([Variations('f', 'alfa'), Or([Variations('f', 'bravo'), Not(Variations('f', 'charlie'))])]))
        
    def test_simplify(self):
        s = fields.Schema(k=fields.ID, v=fields.TEXT)
        ix = RamStorage().create_index(s)
        
        w = ix.writer()
        w.add_document(k=u"1", v=u"aardvark apple allan alfa bear bee")
        w.add_document(k=u"2", v=u"brie glue geewhiz goop julia")
        w.commit()
        
        r = ix.reader()
        q1 = And([Prefix("v", "b", boost=2.0), Term("v", "juliet")])
        q2 = And([Or([Term('v', u'bear', boost=2.0), Term('v', u'bee', boost=2.0),
                      Term('v', u'brie', boost=2.0)]), Term('v', 'juliet')])
        self.assertEqual(q1.simplify(r), q2)
        
    def test_merge_ranges(self):
        q = And([TermRange("f1", u"a", None), TermRange("f1", None, u"z")])
        self.assertEqual(q.normalize(), TermRange("f1", u"a", u"z"))
        
        q = And([NumericRange("f1", None, u"aaaaa"), NumericRange("f1", u"zzzzz", None)])
        self.assertEqual(q.normalize(), q)
        
        q = And([TermRange("f1", u"a", u"z"), TermRange("f1", "b", "x")])
        self.assertEqual(q.normalize(), TermRange("f1", u"a", u"z"))
        
        q = And([TermRange("f1", u"a", u"m"), TermRange("f1", u"f", u"q")])
        self.assertEqual(q.normalize(), TermRange("f1", u"f", u"m"))
        
        q = Or([TermRange("f1", u"a", u"m"), TermRange("f1", u"f", u"q")])
        self.assertEqual(q.normalize(), TermRange("f1", u"a", u"q"))
        
        q = Or([TermRange("f1", u"m", None), TermRange("f1", None, u"n")])
        self.assertEqual(q.normalize(), Every("f1"))
        
        q = And([Every("f1"), Term("f1", "a"), Variations("f1", "b")])
        self.assertEqual(q.normalize(), Every("f1"))
        
        q = Or([Term("f1", u"q"), TermRange("f1", u"m", None), TermRange("f1", None, u"n")])
        self.assertEqual(q.normalize(), Every("f1"))
        
        q = And([Or([Term("f1", u"a"), Term("f1", u"b")]), Every("f1")])
        self.assertEqual(q.normalize(), Every("f1"))
        
        q = And([Term("f1", u"a"), And([Or([Every("f1")])])])
        self.assertEqual(q.normalize(), Every("f1"))
        
    def test_normalize_compound(self):
        def oq():
            return Or([Term("a", u"a"), Term("a", u"b")])
        def nq(level):
            if level == 0:
                return oq()
            else:
                return Or([nq(level-1), nq(level-1), nq(level-1)])
        
        q = nq(7)
        q = q.normalize()
        self.assertEqual(q, Or([Term("a", u"a"), Term("a", u"b")]))
        


if __name__ == '__main__':
    unittest.main()
