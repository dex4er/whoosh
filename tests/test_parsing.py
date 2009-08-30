import unittest
from os import mkdir
from os.path import exists
from shutil import rmtree

from whoosh import fields, index, qparser, query
from whoosh.filedb.filestore import FileStorage

class TestQueryParser(unittest.TestCase):
    def make_index(self, dirname, schema):
        if not exists(dirname):
            mkdir(dirname)
        st = FileStorage(dirname)
        ix = st.create_index(schema)
        return ix
    
    def destroy_index(self, dirname):
        if exists(dirname):
            try:
                rmtree(dirname)
            except OSError:
                pass
    
    def test_andnot(self):
        qp = qparser.QueryParser("content")
        q = qp.parse("this ANDNOT that")
        self.assertEqual(q.__class__.__name__, "AndNot")
        self.assertEqual(q.positive.__class__.__name__, "Term")
        self.assertEqual(q.negative.__class__.__name__, "Term")
        self.assertEqual(q.positive.text, "this")
        self.assertEqual(q.negative.text, "that")
        
        q = qp.parse("foo ANDNOT bar baz")
        self.assertEqual(q.__class__.__name__, "And")
        self.assertEqual(len(q.subqueries), 2)
        self.assertEqual(q[0].__class__.__name__, "AndNot")
        self.assertEqual(q[1].__class__.__name__, "Term")
        
        q = qp.parse("foo fie ANDNOT bar baz")
        self.assertEqual(q.__class__.__name__, "And")
        self.assertEqual(len(q.subqueries), 3)
        self.assertEqual(q[0].__class__.__name__, "Term")
        self.assertEqual(q[1].__class__.__name__, "AndNot")
        self.assertEqual(q[2].__class__.__name__, "Term")
    
    def test_boost(self):
        qp = qparser.QueryParser("content")
        q = qp.parse("this^3 fn:that^0.5 5.67")
        self.assertEqual(q[0].boost, 3.0)
        self.assertEqual(q[1].boost, 0.5)
        self.assertEqual(q[1].fieldname, "fn")
        self.assertEqual(q[2].text, "5.67")
        
    def test_wildcard1(self):
        qp = qparser.QueryParser("content")
        q = qp.parse("hello *the?e* ?star*s? test")
        self.assertEqual(len(q.subqueries), 4)
        self.assertEqual(q[0].__class__.__name__, "Term")
        self.assertEqual(q[0].text, "hello")
        self.assertEqual(q[1].__class__.__name__, "Wildcard")
        self.assertEqual(q[1].text, "*the?e*")
        self.assertEqual(q[2].__class__.__name__, "Wildcard")
        self.assertEqual(q[2].text, "?star*s?")
        self.assertEqual(q[3].__class__.__name__, "Term")
        self.assertEqual(q[3].text, "test")
        
    def test_wildcard2(self):
        qp = qparser.QueryParser("content")
        q = qp.parse("*the?e*")
        self.assertEqual(q.__class__.__name__, "Wildcard")
        self.assertEqual(q.text, "*the?e*")
        
    def test_parse_fieldname_underscores(self):
        s = fields.Schema(my_name=fields.ID(stored=True), my_value=fields.TEXT)
        qp = qparser.QueryParser("my_value", schema=s)
        q = qp.parse("my_name:Green")
        self.assertEqual(q.__class__.__name__, "Term")
        self.assertEqual(q.fieldname, "my_name")
        self.assertEqual(q.text, "Green")
    
    def test_endstar(self):
        qp = qparser.QueryParser("text")
        q = qp.parse("word*")
        self.assertEqual(q.__class__.__name__, "Prefix")
        self.assertEqual(q.text, "word")
        
        q = qp.parse("first* second")
        self.assertEqual(q[0].__class__.__name__, "Prefix")
        self.assertEqual(q[0].text, "first")
    
    def test_escaping(self):
        qp = qparser.QueryParser("text")
        
        q = qp.parse(r'big\small')
        self.assertEqual(q.__class__, query.Term, q)
        self.assertEqual(q.text, "bigsmall")
        
        q = qp.parse(r'big\\small')
        self.assertEqual(q.__class__, query.Term)
        self.assertEqual(q.text, r'big\small')
        
        q = qp.parse(r'http\:example')
        self.assertEqual(q.__class__, query.Term)
        self.assertEqual(q.fieldname, "text")
        self.assertEqual(q.text, "http:example")
        
        q = qp.parse(r'hello\ there')
        self.assertEqual(q.__class__, query.Term)
        self.assertEqual(q.text, "hello there")
        
        q = qp.parse(r'\[start\ TO\ end\]')
        self.assertEqual(q.__class__, query.Term)
        self.assertEqual(q.text, "[start TO end]")
    
        schema = fields.Schema(text=fields.TEXT)
        qp = qparser.QueryParser("text")
        q = qp.parse(r"http\:\/\/www\.example\.com")
        self.assertEqual(q.__class__.__name__, "Term")
        self.assertEqual(q.text, "http://www.example.com")
        
        q = qp.parse("\\\\")
        self.assertEqual(q.__class__.__name__, "Term")
        self.assertEqual(q.text, "\\")
    
    def test_escaping_wildcards(self):
        qp = qparser.QueryParser("text")
        
        q = qp.parse("a*b*c?d")
        self.assertEqual(q.__class__, query.Wildcard)
        self.assertEqual(q.text, "a*b*c?d")
        
        q = qp.parse(u"a*b\\*c?d")
        self.assertEqual(q.__class__, query.Wildcard)
        self.assertEqual(q.text, "a*b*c?d")
        
        q = qp.parse(u"a*b\\\\*c?d")
        self.assertEqual(q.__class__, query.Wildcard)
        self.assertEqual(q.text, u'a*b\\*c?d')
        
        q = qp.parse(u"ab*")
        self.assertEqual(q.__class__, query.Prefix)
        self.assertEqual(q.text, u"ab")
        
        q = qp.parse(u"ab\\\\*")
        self.assertEqual(q.__class__, query.Wildcard)
        self.assertEqual(q.text, u"ab\\*")
        
    def test_phrase(self):
        qp = qparser.QueryParser("content")
        q = qp.parse('"alfa bravo" "charlie delta echo"^2.2 test:"foxtrot golf"')
        self.assertEqual(q[0].__class__.__name__, "Phrase")
        self.assertEqual(q[0].words, ["alfa", "bravo"])
        self.assertEqual(q[1].__class__.__name__, "Phrase")
        self.assertEqual(q[1].words, ["charlie", "delta", "echo"])
        self.assertEqual(q[1].boost, 2.2)
        self.assertEqual(q[2].__class__.__name__, "Phrase")
        self.assertEqual(q[2].words, ["foxtrot", "golf"])
        self.assertEqual(q[2].fieldname, "test")
        
    def test_weird_characters(self):
        qp = qparser.QueryParser("content")
        q = qp.parse(u".abcd@gmail.com")
        self.assertEqual(q.__class__.__name__, "Term")
        self.assertEqual(q.text, u".abcd@gmail.com")
        q = qp.parse(u"r*")
        self.assertEqual(q.__class__.__name__, "Prefix")
        self.assertEqual(q.text, u"r")
        q = qp.parse(u".")
        self.assertEqual(q.__class__.__name__, "Term")
        self.assertEqual(q.text, u".")
        q = qp.parse(u"?")
        self.assertEqual(q.__class__.__name__, "Wildcard")
        self.assertEqual(q.text, u"?")
        
    def test_star(self):
        schema = fields.Schema(text = fields.TEXT(stored=True))
        qp = qparser.QueryParser("text", schema=schema)
        q = qp.parse("*")
        self.assertEqual(q.__class__.__name__, "Prefix")
        self.assertEqual(q.text, u"")
        
        q = qp.parse("*h?ll*")
        self.assertEqual(q.__class__.__name__, "Wildcard")
        self.assertEqual(q.text, u"*h?ll*")
        
        q = qp.parse("h?pe")
        self.assertEqual(q.__class__.__name__, "Wildcard")
        self.assertEqual(q.text, u"h?pe")
        
        q = qp.parse("*? blah")
        self.assertEqual(q.__class__.__name__, "And")
        self.assertEqual(q[0].__class__.__name__, "Wildcard")
        self.assertEqual(q[0].text, u"*?")
        self.assertEqual(q[1].__class__.__name__, "Term")
        self.assertEqual(q[1].text, u"blah")
        
        q = qp.parse("*ending")
        self.assertEqual(q.__class__.__name__, "Wildcard")
        self.assertEqual(q.text, u"*ending")
        
        q = qp.parse("*q")
        self.assertEqual(q.__class__.__name__, "Wildcard")
        self.assertEqual(q.text, u"*q")

    def test_range(self):
        schema = fields.Schema(name=fields.ID(stored=True), text = fields.TEXT(stored=True))
        qp = qparser.QueryParser("text", schema=schema)
        q = qp.parse("Ind* AND name:[d TO]")
        self.assertEqual(q.__class__.__name__, "And")
        self.assertEqual(q[0].__class__.__name__, "Prefix")
        self.assertEqual(q[1].__class__.__name__, "TermRange")
        self.assertEqual(q[0].text, "ind")
        self.assertEqual(q[1].start, "d")
        self.assertEqual(q[1].fieldname, "name")


if __name__ == '__main__':
    unittest.main()
