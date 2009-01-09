#===============================================================================
# Copyright 2008 Matt Chaput
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#===============================================================================

"""This module contains classes for scoring (and sorting) search results.
"""

from __future__ import division
from math import log, sqrt, pi
from array import array


class Weighting(object):
    """The abstract base class for objects that score documents. The base
    object contains a number of collection-level, document-level, and
    result-level statistics for the scoring algorithm to use in its
    calculation (the collection-level attributes are set by set_searcher()
    when the object is attached to a searcher; the other statistics are
    set by set(), which should be called by score()).
    """
    
    #self.doc_count = searcher.doc_count_all()
    #self.index_length = searcher.total_term_count()
    #self.max_doc_freq = ix.max_doc_freq()
    #self.unique_term_count = ix.unique_term_count()
    #self.avg_doc_length = self.index_length / self.doc_count
    
    def idf(self, searcher, fieldnum, text):
        """Calculates the Inverse Document Frequency of the
        current term. Subclasses may want to override this.
        """
        
        # TODO: Cache this?
        df = searcher.doc_frequency(fieldnum, text)
        return log(searcher.doc_count_all() / (df + 1)) + 1.0

    def avg_field_length(self, searcher, fieldnum):
        """Returns the average length of the field per document.
        (i.e. total field length / total number of documents)
        """
        return searcher.field_length(fieldnum) / searcher.doc_count_all()
    
    def l_over_avl(self, searcher, docnum, fieldnum):
        """Returns the length of the current document divided
        by the average length of all documents. This is used
        by some scoring algorithms.
        """
        return searcher.doc_length(docnum) / self.avg_doc_length(searcher, fieldnum)
    
    def fl_over_avfl(self, searcher, docnum, fieldnum):
        """Returns the length of the current field in the current
        document divided by the average length of the field
        across all documents. This is used by some scoring algorithms.
        """
        return searcher.doc_field_length(docnum, fieldnum) / self.avg_field_length(searcher, fieldnum)
    
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        """Calculate the score for a given term in the given
        document. weight is the frequency * boost of the
        term.
        """
        
        raise NotImplementedError
    
# Scoring classes

class BM25F(Weighting):
    """Generates a BM25F score.
    """
    
    def __init__(self, B = 0.75, K1 = 1.2, field_B = None, field_boost = None):
        """B and K1 are free parameters, see the BM25 literature.
        field_B can be a dictionary mapping fieldnums to field-specific B values.
        field_boost can be a dictionary mapping fieldnums to field boost factors.
        """
        
        self.K1 = K1
        self.B = B
        
        if field_B is None: field_B = {}
        self._field_B = field_B
        
        self._field_boost = field_boost

    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        if self._field_boost:
            weight = weight * self._field_boost.get(self.fieldnum, 1.0)
        
        B = self._field_B.get(fieldnum, self.B)
        K1 = self.K1
        idf = self.idf(searcher, fieldnum, text)
        fl_over_avl = self.fl_over_avfl(searcher, docnum, fieldnum)
        
        return idf * (weight + (K1 + 1)) / (weight + K1 * ((1.0 - B) + B * fl_over_avl))

# The following scoring algorithms are translated from classes in
# the Terrier search engine's uk.ac.gla.terrier.matching.models package.

class Cosine(Weighting):
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        idf = self.idf(searcher, fieldnum, text)
        
        DTW = (1.0 + log(weight)) * idf
        QMF = 1.0 # TODO: Fix this
        QTW = ((0.5 + (0.5 * QTF / QMF))) * idf
        return DTW * QTW


class DFree(Weighting):
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        doclen = searcher.doc_length(docnum)
        
        prior = weight / doclen
        post = (weight + 1.0) / doclen
        invprior = searcher.field_length(fieldnum) / searcher.term_count(fieldnum, text)
        norm = weight * log(post / prior, 2)
        
        return 0 - QTF\
                   * norm\
                   * (weight * (- log(prior * invprior, 2))
                      + (weight + 1.0) * (+ log(post * invprior, 2)) + 0.5 * log(post/prior, 2))


class DLH13(Weighting):
    def __init__(self, k = 0.5):
        super(self.__class__, self).__init__()
        self.k = k

    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        k = self.k
        
        dl = searcher.doc_length(docnum)
        f = weight / dl
        tc = searcher.term_count(fieldnum, text)
        doc_count = searcher.doc_count_all()
        avg_doc_length = self.avg_field_length(searcher, fieldnum)
        return 0 - QTF * (weight * log((weight * avg_doc_length / dl) * (doc_count / tc), 2) + 0.5 * log(2.0 * pi * weight * (1.0 - f))) / (weight + k)


class Hiemstra_LM(Weighting):
    def __init__(self, c = 0.15):
        super(self.__class__, self).__init__()
        self.c = c
        
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        c = self.c
        tc = searcher.term_count(fieldnum, text)
        dl = searcher.doc_length(docnum)
        return log(1 + (c * weight * searcher.field_length(fieldnum)) / ((1 - c) * tc * dl))


class InL2(Weighting):
    def __init__(self, c = 1.0):
        super(self.__class__, self).__init__()
        self.c = c
    
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        dl = searcher.doc_length(docnum)
        TF = weight * log(1.0 + (self.c * self.avg_doc_length) / dl)
        norm = 1.0 / (TF + 1.0)
        df = searcher.doc_frequency(fieldnum, text)
        idf_dfr = log((searcher.doc_count_all() + 1) / (df + 0.5), 2)
        
        return TF * idf_dfr * QTF * norm


class TF_IDF(Weighting):
    """Instead of doing any real scoring, this simply returns tf * idf.
    """
    
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        return weight * self.idf(searcher, fieldnum, text)


class Frequency(Weighting):
    """Instead of doing any real scoring, this simply returns the
    term frequency. This may be useful when you don't care about
    normalization and weighting.
    """
    
    def score(self, searcher, fieldnum, text, docnum, weight, QTF = 1):
        return self.searcher.term_count(searcher, fieldnum, text)

# Sorting classes

class FieldSorter(object):
    """Used by searching.Searcher to sort document results based on the
    value of an indexed field, rather than score (see the 'sortfield'
    keyword argument of Searcher.search()).
    
    Upon the first sorted search of a field, this object will build a
    cache of the sorting order for documents based on the values in
    the field. This per-field cache will consume
    (number of documents * size of unsigned int).
    
    Creating the cache will make the first sorted search of a field
    seem slow, but subsequent sorted searches of the same field will
    be much faster.
    """
    
    def __init__(self, searcher, fieldname):
        self.searcher = searcher
        self.fieldname = fieldname
        self.cache = None

    def _create_cache(self):
        searcher = self.searcher
        fieldnum = searcher.fieldname_to_num(self.fieldname)
        
        doc_count = searcher.doc_count
        if doc_count > 65535:
            typecode = "L"
        elif doc_count > 255:
            typecode = "I"
        else:
            typecode = "B"
        
        # Create an array of an unsigned int for every document
        # in the index.
        cache = array(typecode, xrange(0, doc_count))
        
        # For every document containing every term in the field, set
        # its array value to the term's (inherently sorted) position.
        for i, word in enumerate(searcher.lexicon(fieldnum)):
            for docnum, _ in searcher.postings(fieldnum, word):
                cache[docnum] = i
        
        self.limit = i
        self.cache = cache
                
    def doc_orders(self, docnums, reversed = False):
        """Takes a sequence of docnums (produced by query.docs()) and
        yields (docnum, order) tuples. Hence, wrapping this method
        around query.docs() is the sorted equivalent of
        query.doc_scores(), which yields (docnum, score) tuples.
        """
        
        if self.cache is None:
            self._create_cache()
        
        cache = self.cache
        limit = self.limit
        
        if reversed:
            for docnum in docnums:
                yield (docnum, cache[docnum])
        else:
            for docnum in docnums:
                yield (docnum, limit - cache[docnum])
















