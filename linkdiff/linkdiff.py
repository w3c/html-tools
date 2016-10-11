# linkdiff.py
# By Travis Leithead
# 2016/10/05

from HTMLParser import HTMLParser
from difflib import SequenceMatcher

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
        self.matchIndex = -1
        self.matchRatio = 0.0
        self.correctRatio = 0.0
    def __str__(self):
        return '{ ' + ('"id":"' + self.id + '" ' if self.id != '' else '') + '"index":' + str(self.index) + ',"status":"' + self.status + '","href":"' + self.href.encode('ascii', 'xmlcharrefreplace') + '","matchIndex":' + str(self.matchIndex) + ',"matchRatio":' + str(self.matchRatio) + ',"correctRatio":' + str(self.correctRatio) + ',"lineNo":' + str(self.lineNo) + ' }'

HALF_SLIDING_WINDOW_SIZE = 25

def diffLinks(markupBaseline, markupSource):
    parser = LinkAndTextHTMLParser()
    print 'Parsing baseline document...'
    baseDocument = parser.parse(markupBaseline)
    print 'Parsing source document...'
    srcDocument = parser.parse(markupSource)
    print 'Matching links between documents...'
    baseLinkIndex = 0
    baseLinkIndexLen = len(baseDocument.links)
    srcLinkIndex = 0
    srcLinkIndexLen = len(srcDocument.links)
    baseMatches = []
    retryBaselineLinks = []
    retrySourceLinks = []
    while baseLinkIndex < baseLinkIndexLen or srcLinkIndex < srcLinkIndexLen:
        if baseLinkIndex < baseLinkIndexLen:
            srcSlidingWindowIndex = max(srcLinkIndex - HALF_SLIDING_WINDOW_SIZE, 0)
            srcSlidingWindowLimit = min(srcLinkIndex + HALF_SLIDING_WINDOW_SIZE, srcLinkIndexLen)
            while srcSlidingWindowIndex < srcSlidingWindowLimit:
                if check4Match(baseDocument.links[baseLinkIndex], srcDocument.links[srcSlidingWindowIndex]):
                    baseMatches.append(baseDocument.links[baseLinkIndex])
                    break
                srcSlidingWindowIndex += 1
            else:
                retryBaselineLinks.append(baseDocument.links[baseLinkIndex])

            baseLinkIndex += 1
        if srcLinkIndex < srcLinkIndexLen:
            baseSlidingWindowIndex = max(baseLinkIndex - HALF_SLIDING_WINDOW_SIZE, 0)
            baseSlidingWindowLimit = min(baseLinkIndex + HALF_SLIDING_WINDOW_SIZE, baseLinkIndexLen)
            while baseSlidingWindowIndex < baseSlidingWindowLimit:
                if check4Match(baseDocument.links[baseSlidingWindowIndex], srcDocument.links[srcLinkIndex]):
                    baseMatches.append(baseDocument.links[baseSlidingWindowIndex])
                    break
                baseSlidingWindowIndex += 1
            else:
                retrySourceLinks.append(srcDocument.links[srcLinkIndex])

            srcLinkIndex += 1

    print 'Verifying correctness of matched links...'
    for i in xrange(len(baseMatches)):
        check4Correct(baseDocument, baseMatches[i], srcDocument, srcDocument.links[baseMatches[i].matchIndex])

    print 'Last-chance matching previously non-matched links between documents...'
    for baseUnmatchedIndex in xrange(len(retryBaselineLinks)):
        for srcUnmatchedIndex in xrange(len(retrySourceLinks)):
            if check4Match(retryBaselineLinks[baseUnmatchedIndex], retrySourceLinks[srcUnmatchedIndex]):
                check4Correct(baseDocument, retryBaselineLinks[baseUnmatchedIndex], srcDocument, retrySourceLinks[srcUnmatchedIndex])
                break
            elif check4External(retrySourceLinks[srcUnmatchedIndex]):
                retrySourceLinks[srcUnmatchedIndex].status = 'non-matched-external'
        else:
            if check4External(retryBaselineLinks[baseUnmatchedIndex]):
                retryBaselineLinks[baseUnmatchedIndex].status = 'non-matched-external'


MATCH_RATIO_THRESHOLD = 0.7

def check4Match(link1, link2):
    if link1.status[:11] != 'non-matched' or link2.status[:11] != 'non-matched':
        return False
    computedRatio = getAndCompareRatio(link1, link2)
    if computedRatio > MATCH_RATIO_THRESHOLD:
        link1.matchRatio = link2.matchRatio = computedRatio
        link1.status = link2.status = 'matched'
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
IGNORE_LIST['http://test/test/test.com'] = True

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
but then I wouldn't be able to write tests while on the bus.", 'text extraction working correctly')
    
    print 'All tests passed'


runTests()
