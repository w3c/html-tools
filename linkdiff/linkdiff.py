# linkdiff.py
# By Travis Leithead
# 2016/10/05

from HTMLParser import HTMLParser
from difflib import SequenceMatcher
import sys
import os.path
import codecs
import json
import urllib

# Subclass the parser to build the DOM described below. Since the
# DOM will only be used for tracking links and what they link to, the
# only retained nodes are potential link targets (Element objects)
# and links (LinkElement), as well as all text nodes (TextNode).
# Tree-structure is not important, as I only need to worry about what
# text is "before" and "after" a given target. So the parser (as a depth-
# first traversal of markup tags) will let me build a linear representation
# of the start tags that matter and put the text in the right logical
# order for comparison.
class LinkAndTextHTMLParser(HTMLParser):
    """Parses links and text from HTML"""

    def handle_starttag(self, tag, attrs):
        attrNames = [attr[0] for attr in attrs]
        if tag == "a" and "href" in attrNames:
            attrValues = [attr[1] for attr in attrs]
            # an anchor may also have an id and be a link target as well.
            hasId = ""
            if "id" in attrNames:
                hasId = attrValues[attrNames.index("id")]
            link = LinkElement(self.linkCountIndex, attrValues[attrNames.index("href")], HTMLParser.getpos(self)[0], hasId )
            self.linkCountIndex += 1
            self._append_to_head(link)
            self.doc.links.append(link)
            if hasId != "":
                self._append_to_map(hasId, link)
        elif "id" in attrNames:
            attrValues = [attr[1] for attr in attrs]
            elemId = attrValues[attrNames.index("id")]
            elem = Element(elemId)
            self._append_to_head(elem)
            self._append_to_map(elemId, elem)
        else:
            self.doc.droppedTags += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        text = TextNode(data)
        self._append_to_head(text)

    def handle_entityref(self, name):
        self.handle_data("&"+name+";") #pass these through un-modified

    def handle_charref(self, name):
        self.handle_data("&#"+name+";")
        
    def _append_to_head(self, node):
        if self.head == None:
            self.head = node
            self.doc.start = node
        else: #Hook up the bidirectional links
            self.head.next = node
            node.prev = self.head
            self.head = node

    def _append_to_map(self, key, node):
        if key not in self.doc._idMap:
            self.doc._idMap[key] = node

    def parse(self, markup):
        self.doc = Document()
        self.linkCountIndex = 0
        self.head = None
        self.droppedTagCount = 0
        HTMLParser.feed(self, markup)
        HTMLParser.close(self)
        self.head = None
        doc = self.doc
        self.doc = None
        return doc
        
# Document produced by the Parser has the following IDL

# interface Document {
#   readonly attribute LinkElement[] links;
#   readonly attribute Node start;
#   TreeNode getElementById(str id);
#   readonly attribute unsigned long droppedTags;
# };

# interface Node {
#   readonly attribute Node? prev;
#   readonly attribute Node? next;
# };

# interface TextNode : Node {
#   readonly attribute str textContent;
# };

# only nodes with an ID are retained by the parser.
# interface Element : Node {
#   readonly attribute str id; #reflects the id content attribute
# };

# interface LinkElement : Element {
#   readonly attribute unsigned long index;
#   readonly attribute LinkTreeNodeStatus status;
#   readonly attribute str href;
#   readonly attribute long matchIndex;
#   readonly attribute double matchRatio;
#   readonly attribute double correctRatio;
#   readonly attribute unsigned long lineNo;
# };

# enum LinkTreeNodeStatus = {
#   "non-matched",
#   "matched",
#   "correct",
#   "skipped",
#   "broken",
#   "non-matched-external",
#   "matched-external",
#   "correct-external"
# };

class Document:
    def __init__(self):
        self.links = []
        self.start = None
        self._idMap = {}
        self.droppedTags = 0
    def getElementById(self, id):
        if id in self._idMap:
            return self._idMap[id]
        else:
            return None

class Node:
    def __init__(self):
        self.prev = None
        self.next = None

class TextNode(Node):
    def __init__(self, initialText):
        Node.__init__(self)
        self.textContent = initialText
    def __str__(self):
        return "text<"+self.textContent[:40]+ ( "..." if len(self.textContent) > 40 else "" ) + "> (len:"+str(len(self.textContent))+")"

class Element(Node):
    def __init__(self, elemId):
        Node.__init__(self)
        self.id = elemId
    def __str__(self):
        return '{ "id":"' + self.id.encode('ascii', 'xmlcharrefreplace') + '" }' #because attrs have their entites handled by the parser, and ascii output may not handle them.

class LinkElement(Element):
    def __init__(self, index, href, lineNo, elemId):
        Element.__init__(self, elemId)
        self.index = index
        self.href = href
        self.lineNo = lineNo
        self.status = "non-matched"
        self._matched = False #convenience for rapid testing (vs. substring ops)
        self.matchIndex = -1
        self.matchRatio = 0.0
        self.correctRatio = 0.0
    def __str__(self):
        return '{ ' + ('"id":"' + self.id + '" ' if self.id != '' else '') + '"index":' + str(self.index) + ',"status":"' + self.status + '","href":"' + self.href.encode('ascii', 'xmlcharrefreplace') + '","matchIndex":' + str(self.matchIndex) + ',"matchRatio":' + str(self.matchRatio) + ',"correctRatio":' + str(self.correctRatio) + ',"lineNo":' + str(self.lineNo) + ' }'

SLIDING_WINDOW_SIZE = 50
SHOW_STATUS = True

def diffLinks(markupBaseline, markupSource):
    parser = LinkAndTextHTMLParser()
    if SHOW_STATUS:
        print 'Parsing baseline document...'
    baseDocument = parser.parse(markupBaseline)
    if SHOW_STATUS:
        print 'Parsing source document...'
    srcDocument = parser.parse(markupSource)
    if SHOW_STATUS:
        print 'Matching links between documents...'
    baseLinkIndex = 0
    baseLinkIndexLen = len(baseDocument.links)
    srcLinkIndex = 0
    srcLinkIndexLen = len(srcDocument.links)
    baseMatches = [] # this collects matches for both sides (the source-side is reachable via the base's matchIndex value)
    retryBaselineLinks = []
    retrySourceLinks = []
    while baseLinkIndex < baseLinkIndexLen or srcLinkIndex < srcLinkIndexLen:
        if baseLinkIndex < baseLinkIndexLen:
            srcSlidingWindowIndex = srcLinkIndex
            srcSlidingWindowLimit = min(srcLinkIndex + SLIDING_WINDOW_SIZE, srcLinkIndexLen)
            while srcSlidingWindowIndex < srcSlidingWindowLimit:
                if check4Match(baseDocument.links[baseLinkIndex], srcDocument.links[srcSlidingWindowIndex]):
                    baseMatches.append(baseDocument.links[baseLinkIndex])
                    # Assume this is a new "synchronization point" between the documents
                    # Skip intervening links (for later) and advance indexes.
                    while srcLinkIndex < srcSlidingWindowIndex:
                        retrySourceLinks.append(srcDocument.links[srcLinkIndex])
                        srcLinkIndex += 1
                    srcLinkIndex = srcSlidingWindowIndex + 1 #start the next iteration on the next (un-matched) link
                    break
                srcSlidingWindowIndex += 1
            else:
                retryBaselineLinks.append(baseDocument.links[baseLinkIndex])
            baseLinkIndex += 1
        if srcLinkIndex < srcLinkIndexLen:   
            baseSlidingWindowIndex = baseLinkIndex
            baseSlidingWindowLimit = min(baseLinkIndex + SLIDING_WINDOW_SIZE, baseLinkIndexLen)
            while baseSlidingWindowIndex < baseSlidingWindowLimit:
                if check4Match(baseDocument.links[baseSlidingWindowIndex], srcDocument.links[srcLinkIndex]):
                    baseMatches.append(baseDocument.links[baseSlidingWindowIndex])
                    while baseLinkIndex < baseSlidingWindowIndex:
                        retryBaselineLinks.append(baseDocument.links[baseLinkIndex])
                        baseLinkIndex += 1
                    baseLinkIndex = baseSlidingWindowIndex + 1
                    break
                baseSlidingWindowIndex += 1
            else:
                retrySourceLinks.append(srcDocument.links[srcLinkIndex])
            srcLinkIndex += 1
    if SHOW_STATUS:
        print 'Verifying correctness of matched links...'
    for i in xrange(len(baseMatches)):
        check4Correct(baseDocument, baseMatches[i], srcDocument, srcDocument.links[baseMatches[i].matchIndex])
    if SHOW_STATUS:
        print 'Last-chance matching previously non-matched links between documents...'
    for baseUnmatchedIndex in xrange(len(retryBaselineLinks)):
        for srcUnmatchedIndex in xrange(len(retrySourceLinks)):
            if check4Match(retryBaselineLinks[baseUnmatchedIndex], retrySourceLinks[srcUnmatchedIndex]):
                check4Correct(baseDocument, retryBaselineLinks[baseUnmatchedIndex], srcDocument, retrySourceLinks[srcUnmatchedIndex])
                del retrySourceLinks[srcUnmatchedIndex] # Since we don't need to re-check this instance (it's now matched)
                break
            elif check4External(retrySourceLinks[srcUnmatchedIndex]):
                retrySourceLinks[srcUnmatchedIndex].status = 'non-matched-external'
        else:
            if check4External(retryBaselineLinks[baseUnmatchedIndex]):
                retryBaselineLinks[baseUnmatchedIndex].status = 'non-matched-external'
    return (baseDocument, srcDocument)

MATCH_RATIO_THRESHOLD = 0.7

def check4Match(link1, link2):
    if link1._matched or link2._matched:
        return False
    computedRatio = getAndCompareRatio(link1, link2)
    if computedRatio > MATCH_RATIO_THRESHOLD:
        link1.matchRatio = link2.matchRatio = computedRatio
        link1.status = link2.status = 'matched'
        link1._matched = link2._matched = True
        link1.matchIndex = link2.index
        link2.matchIndex = link1.index
        return True
    if computedRatio > link1.matchRatio:
        link1.matchRatio = computedRatio
        link1.matchIndex = link2.index
    if computedRatio > link2.matchRatio:
        link2.matchRatio = computedRatio
        link2.matchIndex = link1.index
    return False

IGNORE_LIST = {}

# Only called after a pair of links has been matched. This "upgrades" the match (if possible) to an 
# additional state: skipped, correct, correct-external, broken, or the [non-upgrade] matched-external.
def check4Correct(doc1, link1, doc2, link2):
    if link1.href in IGNORE_LIST or link2.href in IGNORE_LIST:
        if link1.href in IGNORE_LIST:
            link1.status = 'skipped'
        if link2.href in IGNORE_LIST:
            link2.status = 'skipped'
        return
    if check4External(link1) or check4External(link2):
        if check4External(link1) and check4External(link2):
            if link1.href == link2.href:
                link1.status = link2.status = 'correct-external'
                link1.correctRatio = link2.correctRatio = 1.0
            else:
                link1.status = link2.status = 'matched-external'
        elif check4External(link1):
            link1.status = 'matched-external'
        else:
            link2.status = 'matched-external'
        return
    link1dest = doc1.getElementById(getLinkTarget(link1.href))
    link2dest = doc2.getElementById(getLinkTarget(link2.href))
    if link1dest == None or link2dest == None:
        if link1dest == None:
            link1.status = 'broken'
        if link2dest == None:
            link2.status = 'broken'
        return
    destCmpRatio = getAndCompareRatio(link1dest, link2dest)
    link1.correctRatio = link2.correctRatio = destCmpRatio
    if destCmpRatio > MATCH_RATIO_THRESHOLD:
        link1.status = link2.status = 'correct'


def getAndCompareRatio(elem1, elem2):
    text1 = getContextualText(elem1)
    text2 = getContextualText(elem2)
    matcher = SequenceMatcher(lambda x: x in ' \t', text1, text2)
    ratio = matcher.quick_ratio()
    if ratio >= 0.5 and ratio < 0.9:
        ratio = matcher.ratio()
    return ratio


HALF_CONTEXT_MIN = 150

def getContextualText(elem):
    beforeText = ''
    beforeCount = 0
    afterText = ''
    afterCount = 0
    runner = elem
    while beforeCount < HALF_CONTEXT_MIN and runner != None:
        if isinstance(runner, TextNode):
            beforeText = runner.textContent + beforeText
            beforeCount += len(runner.textContent)
        runner = runner.prev

    runner = elem
    while afterCount < HALF_CONTEXT_MIN and runner != None:
        if isinstance(runner, TextNode):
            afterText += runner.textContent
            afterCount += len(runner.textContent)
        runner = runner.next

    return beforeText[-150:] + afterText[:150]


def check4External(link):
    if link.href[0:1] != '#':
        return True
    return False


def getLinkTarget(href):
    return href[1:]

# Validation testing
# =====================================================
def istrue(a, b, message):
    if not a == b:
        raise ValueError("Test assertion failed: " + message)

def dumpDocument(doc, enumAll=False):
    print "----------------"
    print "Document summary"
    print "----------------"
    print "droppedTags: " + str(doc.droppedTags)
    print "number of links in collection: " + str(len(doc.links))
    print "number of addressable ids: " + str(len(doc._idMap.keys()))
    if enumAll == True:
        print "enumeration of nodes in start:"
    head = doc.start
    counter = 0
    while head != None:
        if enumAll == True:
            print "  " + str(counter) + ") " + str(head)
        head = head.next
        counter += 1
    print "total nodes in document: " + str(counter)
    
def runTests():
    global SHOW_STATUS #intend to modify a global variable.
    oldShowStatus = SHOW_STATUS
    SHOW_STATUS = False
    IGNORE_LIST['http://test/test/test.com'] = True
    
    # test 1
    parser = LinkAndTextHTMLParser()
    doc = parser.parse("<hello/><there id ='foo' /></there></hello>");
    istrue(doc.droppedTags, 1, "test1: expected only one dropped tag")
    istrue(doc.start.id, 'foo', "test1: expected 1st retained element to have id 'foo'")
    istrue(doc.start.next, None, "test1: element initialized correctly")
    istrue(doc.getElementById('foo'), doc.start, "test1: document can search for an element by id")
    istrue(doc.getElementById('foo2'), None, "test1: document fails to retrieve non-existant id")
    istrue(len(doc.links), 0, "test1: no links were found")
    #dumpDocument(doc, True)

    # test 2
    doc = parser.parse('<a id="yes" test=one href="http://test.com/file.htm#place">link text sample</a>')
    istrue(doc.droppedTags, 0, "test2: no dropped tags")
    istrue(len(doc.links), 1, "test2: link element was placed into the links collection")
    istrue(doc.links[0], doc.start, "test2: the first link is also the start of the document")
    istrue(doc.start.id, "yes", "test2: link elements can also have an id")
    istrue(doc.start.next.textContent, "link text sample", "test2: a text node was properly appended to the start of the document")
    istrue(doc.start.next.next, None, "test2: only two items in the document's start list")
    istrue(doc.start.index, 0, "test2: link's index is 0")
    istrue(doc.start.href, "http://test.com/file.htm#place", "test2: retained the URL")
    #dumpDocument(doc, True)

    # test 3
    doc = parser.parse(u'plain text &copy; with &#68; in it<span id="&pound;"></span><a href="#&copy;">text</a>')
    istrue(doc.droppedTags, 0, "test3: no dropped tags")
    istrue(doc.start.next.textContent, "&copy;", "test3: html entity ref unescaped in text")
    istrue(doc.getElementById("&pound;"), None, "test3: html entity ref escaped by parser")
    istrue(doc.getElementById(u"\xa3"), doc.start.next.next.next.next.next, "test3: using the unicode value finds the escaped entity ref by id")
    istrue(doc.start.next.next.next.next.next.next.next.next, None, "test3: only 8 items in the list")
    istrue(doc.start.next.next.next.next.next.next.index, 0, "test3: 2nd-to-last item in the list has 0th index")
    istrue(doc.start.next.next.next.next.next.next, doc.links[0], "test3: the link was indexed appropriately")
    istrue(doc.links[0].href, u"#\xa9", "test3: href value with entity-ref converted to unicode by the parser")
    #dumpDocument(doc, True)
    
    # test 4
    doc = parser.parse(u'<div id="&copy;"></div><a href="#&copy;"></a>')
    istrue(doc.getElementById(doc.links[0].href[1:]), doc.start, "test4: unicode attribute handling and escaping is self-consistent for lookups")
    #dumpDocument(doc, True)
    
    # test 5
    doc = parser.parse('<div id="target">first</div><div id="target">second</div><a href="#target"></a>')
    istrue(doc.getElementById('target'), doc.start, 'test5: for duplicate ids, link targets (and getElementById) should ignore all but the first ocurence in document order')
    #dumpDocument(doc, True)
    
    # test 6 - getContextualText
    doc = parser.parse("The <b>freeway</b> can get quite backed-up; that's why I enjoy riding the <div id=target>Connector</div>. It saves me \n\
lots of time on my commute. Microsoft <i>is quite awesome</i> to provide such a service to their <span class=employee><a>employees</a></span> \n\
that live in the <span>Pugot Sound</span> area. Of course, I could get to work a lot faster by driving my car,\n\
but then I wouldn't be able to write tests while on the <a href=#target>bus</a>.")
    istrue(getContextualText(doc.links[0]), " live in the Pugot Sound area. Of course, I could get to work a lot faster by driving my car,\n\
but then I wouldn't be able to write tests while on the bus.", "test6: text extraction working correctly")
    istrue(getContextualText(doc.getElementById("target")), "The freeway can get quite backed-up; that's why I enjoy riding the Connector. It saves me \n\
lots of time on my commute. Microsoft is quite awesome to provide such a service to their employees \n\
that live in the Pugot So", "test6: target text extraction")
    
    # test 7 - getAndCompareRatio
    doc = parser.parse("Here's some text that is the same<a href=hi>")
    doc2 = parser.parse("And this sentance won't match up anywhere<a href=bar>")
    istrue(getAndCompareRatio(doc.links[0], doc.links[0]), 1.0, "test7: getAndCompareRatio working for same sentances")
    istrue(getAndCompareRatio(doc.links[0], doc2.links[0]) < 0.09, True, "test7: getAndCompareRatio working for non-similar sentances")
    doc2 = parser.parse("Here's some text that isn't the same<a href=foo>")
    istrue(getAndCompareRatio(doc.links[0], doc2.links[0]) > 0.95, True, "test7: getAndCompareRatio working for similar sentances")
    
    # test 8 - check4Match(link1, link2)
    istrue(check4Match(doc.links[0], doc2.links[0]), True, "test8: check4Match finds the two links that are similar a match!")
    istrue(doc.links[0].status, "matched", "test8: link status updated to 'matched'")
    istrue(doc.links[0].status, doc2.links[0].status, "test8: both status' are the same in match case")
    istrue(doc2.links[0].matchRatio > 0.95, True, "test8: matchRatio set to the result of the match")
    istrue(doc.links[0].matchIndex, 0, "test8: match index correct for matching link in other document")
    istrue(check4Match(doc.links[0], doc2.links[0]), False, "test8: check4Match doesn't re-process links that have already been matched")

    # test 9 - put it all together
    markup1 = "<a href=#top>Top</a>: <a href=http://test/test/test.com>if</a> you're <a href='http://external/comparing'>comparing lines</a> \
as sequences of characters, and don't want to <a href=#sync>synch</a> up on blanks or hard <span id='sync'>tabs</span>. \
The optional arguments a and b are sequences to be compared; both <tt>default</tt> to empty strings. The elements of both sequences must be hashable. \
The optional argument autojunk can be used to disable the automatic <a href=#not_matched>junk heuristic</a>. \
New in version 2.7.1: The <a href='http://test/test/test.com'>autojunk</a> parameter.."
    markup2 = "<a href=#top>Top</a>: <a href=http://test/test/test.com>if</a> you are <a href='http://external/comparing'>comparing a line</a> \
as sequences of characters, and don't want to <a href=#sync>synch</a> up on <i>blanks</i> or <b>hard <span id='sync'>tabs</span></b>. \
The optional arguments a and b are sequences to be compared; both will <tt>default</tt> to empty strings. The elements of both sequences must be hashable--the \
optional argument autoskip may stop the automatic skipping behavior for the <a href=#not_matched>stop algorithm</a>. \
With the addition of a new stop algorithm in this document, you may now see that things aren't quite <a href='http://test/test/test.com'>the same</a>.."
    doc, doc2 = diffLinks(markup1, markup2)
    istrue(len(doc.links), 6, "test9: parsing validation-- 6 links in markup1")
    istrue(len(doc2.links), 6, "test9: parsing validation-- 6 links in markup2")
    istrue(doc.links[0].status, "broken", "test9: link matching validation: link is broken")
    istrue(doc.links[0].matchIndex, 0, "test9: link matching validation: matched at 0")
    istrue(doc2.links[doc.links[0].matchIndex].href, "#top", "test9: correct link (0) matched in source doc")
    istrue(doc.links[0].matchRatio > 0.97, True, "test9: link matching validation: Ratio is 0.97333-ish")
    istrue(doc.links[0].correctRatio, 0.0, "test9: link matching validation: default value for not-correct")
    istrue(doc.links[1].status, "skipped", "test9: link matching validation: link is matched & skipped")
    istrue(doc.links[1].matchIndex, 1, "test9: link matching validation: matched at 1")
    istrue(doc2.links[doc.links[1].matchIndex].href, "http://test/test/test.com", "test9: correct link (1) matched in source doc")
    istrue(doc.links[1].matchRatio > 0.98, True, "test9: link matching validation: Ratio is 0.9806")
    istrue(doc.links[1].correctRatio, 0.0, "test9: link matching validation: not correct--0 ratio")
    istrue(doc.links[2].status, "correct-external", "test9: link matching validation: link is correct, but external")
    istrue(doc.links[2].matchIndex, 2, "test9: link matching validation: matched at 2")
    istrue(doc2.links[doc.links[2].matchIndex].href, "http://external/comparing", "test9: correct link (2) matched in source doc")
    istrue(doc.links[2].matchRatio > 0.97, True, "test9: link matching validation: Ratio is 0.97885-ish")
    istrue(doc.links[2].correctRatio, 1.0, "test9: link matching validation: external link is 100% correct/same")
    istrue(doc.links[3].status, "correct", "test9: link matching validation: link is correct")
    istrue(doc.links[3].matchIndex, 3, "test9: link matching validation: matched at 3")
    istrue(doc2.links[doc.links[3].matchIndex].href, "#sync", "test9: correct link (2) matched in source doc")
    istrue(doc.links[3].matchRatio > 0.96, True, "test9: link matching validation: Ratio is approx 0.969")
    istrue(doc.links[3].correctRatio > 0.97, True, "test9: link matching validation: Correctness matching ratio is approx 0.9725")
    istrue(doc.links[4].status, "non-matched", "test9: link matching validation: link is not matched")
    istrue(doc.links[4].matchIndex, 5, "test9: link matching validation: failed to match--all broken links checked, index set to last index")
    istrue(doc.links[4].matchRatio < 0.151, True, "test9: link matching validation: Match ratio is too low to match, approx 0.150")
    istrue(doc.links[4].correctRatio, 0.0, "test9: link matching validation: un-matched correctRatio is 0.0")
    istrue(doc.links[5].status, "non-matched-external", "test9: link matching validation: link is not matched and external")
    istrue(doc.links[5].matchIndex, 4, "test9: link matching validation: matched at 4")
    istrue(doc.links[5].matchRatio < 0.2, True, "test9: link matching validation: not matched, low ratio (0.192)")
    istrue(doc.links[5].correctRatio, 0.0, "test9: link matching validation: Correctness n/a (0.0)")
    #dumpDocument(doc, True) 
    #dumpDocument(doc2, True) 
    
    # test 10 - check 'matched' and 'matched-external'
    markup1 =  "<span id=matched>One</span> of the common, difficult to figure-out problems in the current HTML spec is\n"
    markup1 += "whether links are 'correct'. Not 'correct' as in syntax or as opposite to broken\n"
    markup1 += "links, but rather that the link in question goes to the semantically correct place\n"
    markup1 += "in the spec or other linked <a href='http://external/place1'>spec</a>. <a href=#matched>Correctness</a>, in this sense, can only be determined\n"
    markup1 += "by comparing the links to a canonical 'correct' source. In the case of the W3C HTML\n"
    markup1 += "spec, the source used for determining correctness is the WHATWG version of the spec."

    markup2 =  "One of the common, difficult to figure-out problems in the current HTML spec is\n"
    markup2 += "whether links are 'correct'. Not 'correct' as in syntax or as opposite to broken\n"
    markup2 += "links, but rather that the link in question goes to the semantically correct place\n"
    markup2 += "in the spec or other linked <a href='http://external/place2'>spec</a>. <a href=#matched>Correctness</a>, in this sense, can only be determined\n"
    markup2 += "by comparing the links to a canonical 'correct' source. In the case of the W3C HTML\n"
    markup2 += "spec, the source used for determining correctness is the WHATWG <span id=matched>version</span> of the spec."
    doc, doc2 = diffLinks(markup1, markup2)
    istrue(len(doc.links), 2, "test10: parsing validation-- 2 links in markup1")
    istrue(len(doc2.links), 2, "test10: parsing validation-- 2 links in markup2")
    istrue(doc.links[0].status, "matched-external", "test10: link matching validation: link is matched, but external (and not correct)")
    istrue(doc.links[0].matchIndex, 0, "test10: link matching validation: matched at 0")
    istrue(doc2.links[doc.links[0].matchIndex].href, "http://external/place2", "test10: correct index (0) matched in source doc")
    istrue(doc.links[0].matchRatio > 0.99, True, "test10: link matching validation: Ratio is 1.0")
    istrue(doc.links[0].correctRatio, 0.0, "test10: link matching validation: default value for not-correct")
    istrue(doc.links[0].lineNo, 4, "test10: line number is correct (4)")
    istrue(doc.links[1].status, "matched", "test10: link matching validation: link is matched")
    istrue(doc.links[1].matchIndex, 1, "test10: link matching validation: matched at 1")
    istrue(doc2.links[doc.links[1].matchIndex].href, "#matched", "test10: correct link (1) matched in source doc")
    istrue(doc.links[1].matchRatio > 0.99, True, "test10: link matching validation: Ratio is 1.0")
    istrue(doc.links[1].correctRatio < 0.28, True, "test10: link matching validation: not correct--0.275 ratio")
    #dumpDocument(doc, True)
    print 'All tests passed'
    SHOW_STATUS = oldShowStatus

# Input processing
# =====================================================

def cmdhelp():
    print "linkdiff - A diffing tool for HTML hyperlink semantic validation"
    print ""
    print "  The tool compares the hyperlinks (anchor tags with an href attribute) in a baseline"
    print "  document with those in a source document. It checks that both documents have the same"
    print "  set of hyperlinks, and that those hyperlinks link to the same relative places within"
    print "  their respective documents."
    print ""
    print "Usage:"
    print ""
    print "  linkdiff [flags] <baseline html file> <source html file>"
    print ""
    print "      The baseline and source files may be paths to the respective files on disk, or URLs."
    print "      The only supported protocols for URLs are 'http' and 'https'; any other protocol will"
    print "      be interpreted as a local file path."
    print ""
    print "Flags:"
    print "  -ratio <value between 0 and 1>"
    print "      Example: linkdiff -ratio 0.9 baseline_doc.html source_doc.html"
    print "      Overrides the default ratio used for verifying that a link is in the same place in"
    print "      both specs, and that the hyperlink's targets are in the same relative place. A low"
    print "      ratio (e.g., 0.25 or 25%) is more permissive in that only 25% of the relative surrounding"
    print "      content must be the same to be considered a match. A higher ratio (e.g., 0.9 or 90%) is"
    print "      more strict. The default (if the flag is not supplied) is 0.7 or 70%."
    print "  -ignorelist <ignorelist_file>"
    print "      Example: linkdiff -ignorelist ignore_list.json baseline_doc.html source_doc.html"
    print "      The ignore list is a file containing a JSON object with a single property named"
    print "      'ignoreList' whose value is an array of strings. The strings should contain the absolute"
    print "      or relative URLs to skip/ignore during link verification. String matching is used to"
    print "      apply the strings to href values, so exact matches are required. The ignore list applies"
    print "      to both baseline and source html files"
    print "  -V"
    print "      Example: linkdiff -V baseline_doc.html source_doc.html"
    print "      Turns off the verbose status messages during processing."
    print "  -runtests"
    print "      Example: linkdiff -runtests"
    print "      When this flag is used, the <baseline html file> and <source html file> input values"
    print "      are not required. This flag runs the self-tests to ensure the code is working as expected"

# Test for existance before calling...may return None as failure mode
def getFlagValue(flag):
    index = sys.argv.index(flag)
    if index + 1 < len(sys.argv)-2: # [0] linkdiff [len-2] baseline_doc [len-1] src_doc
        return sys.argv[index+1]
    else:
        return None

def setRatio(newRatio):
    global MATCH_RATIO_THRESHOLD
    if newRatio == None:
        return
    newRatio = float(newRatio)
    # clamp from 0..1
    newRatio = max(min(newRatio, 1.0), 0.0)
    MATCH_RATIO_THRESHOLD = newRatio
    if SHOW_STATUS:
        print "Using custom ratio: " + str(MATCH_RATIO_THRESHOLD)


def toUnicode(raw):
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode("utf-16", "replace")
    elif raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig", "replace") #decoding errors substitute the replacement character
    else:
        return raw.decode("utf-8", "replace") # assume it.
    
def getTextFromLocalFile(fileString):
    if fileString[0:1] == '"':
        fileString = fileString[1:-1]
    normalizedfileString = os.path.abspath(fileString)
    if not os.path.isfile(normalizedfileString):
        print "File not found: '" + fileString + "' is not a file (or was not found)"
        return None
    with open(fileString, "r") as file:
        return toUnicode(file.read())
    
def setIgnoreList(newListFile):
    global IGNORE_LIST
    if newListFile == None:
        return
    ignoreRoot = json.loads(getTextFromLocalFile(newListFile))
    if not "ignoreList" in ignoreRoot:
        print "Ignore list format error: expected an root object with key 'ignoreList'"
        return
    listOIgnoreVals = ignoreRoot["ignoreList"]
    if not isinstance(listOIgnoreVals, list): #check for built-in list type.
        print "Ignore list format error: expected the 'ignoreList' key to have a list as its value"
        return
    counter = 0
    for ignoreItem in listOIgnoreVals:
        if isinstance(ignoreItem, basestring):
            IGNORE_LIST[ignoreItem] = True
            counter += 1
    if SHOW_STATUS:
        print "Using ignore list; entries found: " + str(counter)
    
def hideStatus():
    global SHOW_STATUS
    SHOW_STATUS = False

def loadURL(url):
    try:
        urlhandle = urllib.urlopen(url)
        if SHOW_STATUS:
            print "Getting '" + url + "' from the network..."
        contents = toUnicode(urlhandle.read())
        urlhandle.close()
        return contents
    except IOError:
        print "Error opening network location: " + url
        return None

def loadDocumentText(urlOrPath):
    if urlOrPath[0:1] == '"':
        urlOrPath = urlOrPath[1:-1]
    if urlOrPath[:7] == "http://" or urlOrPath[:8] == "https://":
        return loadURL(urlOrPath)
    else: #assume file path...
        return getTextFromLocalFile(urlOrPath) # may return None

def processCmdParams():        
    if len(sys.argv) == 1:
        return cmdhelp()
    if "-runtests" in sys.argv:
        return runTests()
    expectedArgs = 3
    if "-V" in sys.argv:
        hideStatus()
        expectedArgs += 1
    if "-ratio" in sys.argv:
        setRatio(getFlagValue("-ratio"))
        expectedArgs += 2
    if "-ignorelist" in sys.argv:
        setIgnoreList(getFlagValue("-ignorelist"))
        expectedArgs += 2
    if len(sys.argv) < expectedArgs:
        print "Usage error: <baseline_doc.html> and <source_doc.html> parameters required."
    
    # get baseline and source text from their files...
    baseDocText = loadDocumentText(sys.argv[expectedArgs-2])
    if baseDocText == None:
        return
    sourceDocText = loadDocumentText(sys.argv[expectedArgs-1])
    if sourceDocText == None:
        return
    baseDoc, sourceDoc = diffLinks(baseDocText, sourceDocText)
    
    
processCmdParams()
        
        
