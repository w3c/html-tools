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
import time
from multiprocessing import Process, Pool, Value, Manager
import re
import multiprocessing
import thread

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
        HTMLParser.reset(self) # among other things, resets the line numbering :-)
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
#            attribute LinkTreeNodeStatus status;
#   readonly attribute str href;
#            attribute long matchIndex;
#            attribute double matchRatio;
#            attribute double correctRatio;
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
        #self.index #added during indexing! hash of "word" <-> [0:count, 1-n:link index]
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
        self._cachedContextualText = None
    def __str__(self):
        return '{ "id":"' + self.id.encode('ascii', 'xmlcharrefreplace') + '" }' #because attrs have their entites handled by the parser, and ascii output may not handle them.

class LinkElement(Element):
    def __init__(self, index, href, lineNo, elemId):
        Element.__init__(self, elemId)
        self.index = index
        self.href = href
        self.lineNo = lineNo
        self.resetMatchStatus()
        #self.words #added during indexing!
    def resetMatchStatus(self):
        self.status = "non-matched"
        self._matched = False #convenience for rapid testing (vs. substring ops)
        self.matchIndex = -1
        self.matchRatio = 0.0
        self.correctRatio = 0.0
    def __str__(self):
        return '{' + '"index":' + str(self.index) + ',"matchIndex":' + str(self.matchIndex) + ',"matchRatio":' + str(self.matchRatio)[:5] + ',"correctRatio":' + str(self.correctRatio)[:5] + ',"lineNo":' + str(self.lineNo) + ',"status":"' + self.status + '","href":"' + self.href.encode('ascii', 'xmlcharrefreplace') + '"' + (',"id":"' + self.id + '"' if self.id != '' else '') + '}'
        
CPU_COUNT = multiprocessing.cpu_count()

class Job:
    def __init__(self, baseDoc, baseIndex, srcDoc, suggestedStartIndex):
        self.baseIndex = baseIndex
        self.baseDoc = baseDoc
        self.baseElem = baseDoc.links[baseIndex]
        self.srcDoc = srcDoc
        self.srcInitialIndex = suggestedStartIndex
        self.isRunning = False #does the job need to be (re-)started?
        self.hasResults = False
        self.matcher = SequenceMatcher(lambda x: x in ' \t')
        self.matcher.sequence2Text = getContextualText(self.baseElem)
        self.matcher.set_seq2(self.matcher.sequence2Text)
        self.matched = False # True and the following data applies:
        self.baseStatus = "non-matched"
        self.srcStatus = "non-matched"
        self.bestSrcIndex = None # or an index into the srcDocument's link array
        self.bestMatchRatio = 0.0 # the match ratio
        self.correctRatio = 0.0
    def replace(self, baseIndex, suggestedStartIndex):
        self.__init__(self.baseDoc, baseIndex, self.srcDoc, suggestedStartIndex)

class LocalYieldingJob(Job):
    def __init__(self, baseDoc, baseIndex, srcDoc, suggestedStartIndex = 0):
        Job.__init__(self, baseDoc, baseIndex, srcDoc, suggestedStartIndex)
        self.resumeOffset = suggestedStartIndex
    def start(self):
        self.isRunning = True
        checked = 0
        while checked < SLIDING_WINDOW_SIZE and (checked == 0 or self.resumeOffset != self.srcInitialIndex):
            srcElem = self.srcDoc.links[self.resumeOffset]
            if check4Match(self, srcElem):
                check4Correct(self, srcElem)
                self.hasResults = True
                break
            self.resumeOffset = (self.resumeOffset + 1) % len(self.srcDoc.links) # wrap around at the length of the array.
            checked += 1
        if self.resumeOffset == self.srcInitialIndex:
            if not self.matched and check4External(self.baseElem):
                self.baseStatus = "non-matched-external"
            self.hasResults = True # not-found results :)
        elif checked == SLIDING_WINDOW_SIZE:
            self.isRunning = False # yielding... running stays true for final results

class BackgroundContinuousJob(Job):
    def __init__(self, baseDoc, baseIndex, srcDoc, suggestedStartIndex = 0):
        Job.__init__(self, baseDoc, baseIndex, srcDoc, suggestedStartIndex)
    def start(self):
        thread.start_new_thread(threadedRemoteJobProcessor, (self,))
        self.isRunning = True

def threadedRemoteJobProcessor(job):
    index = job.srcInitialIndex
    firstTime = True
    while firstTime or index != job.srcInitialIndex:
        srcElem = job.srcDoc.links[index]
        if check4Match(job, srcElem):
            check4Correct(job, srcElem)
            break
        index = (index + 1) % len(job.srcDoc.links) # wrap around at the length of the array.
        firstTime = False
    else: #not matched
        if check4External(job.baseElem):
            job.baseStatus = "non-matched-external"
    job.hasResults = True

jobQueue = []

SLIDING_WINDOW_SIZE = 50
SHOW_STATUS = False

def percentComplete(numerator, denomator):
    return "  " + str( float(numerator) / float(denomator) * 100 )[:4] + "% complete..."

def parseTextToDocument(htmlText, statusText):
    parser = LinkAndTextHTMLParser()
    if SHOW_STATUS:
        print statusText
    return parser.parse(htmlText)

# index is a hashtable of "name" <-> [0:count,1-n:list of matching link indexes]
def buildIndex(doc, statusText):
    if SHOW_STATUS:
        print statusText
    doc.index = {}
    tooCommon = []
    #if more than 1/3 of all links have this word, then it's too common! #Consider using sqrt instead (exponential)
    tooCommonThreshold = len(doc.links) / 3 if len(doc.links) > 2 else 1 # int division, <3 yeilds 0 for too common!
    # slice the text in the document up into words and attach (HALF_WORD_COUNT * 2) number of words to each link
    for linkIndex in xrange(len(doc.links)):
        link = doc.links[linkIndex]
        wordsList = getDirectionalContextualWords(link, True) + getDirectionalContextualWords(link, False)
        link.words = wordsList
        for word in wordsList:
            if word in tooCommon:
                continue
            if word in doc.index:
                doc.index[word][0] += 1 # bump the count
                doc.index[word].append(linkIndex)
                if doc.index[word][0] > tooCommonThreshold:
                    tooCommon.append(word)
                    del doc.index[word] # remove it from the index
            else:
                doc.index[word] = [1, linkIndex]
    #print "Too Common: " + str(len(tooCommon)) + " -- " + str(tooCommon)
    #print "Total unique words: " + str(len(doc.index.keys()))
    #ave = 0
    #for key in doc.index.keys():
    #    ave += doc.index[key][0]
    #print "Average occurances/word: " + str(ave/float(len(doc.index.keys())))

# Returns a tuple of documents associated with the baseline, source documents.
def diffLinks(baseDocument, srcDocument, stats):
    stats["matchingLinksTotal"] = 0
    srcLinkIndexLen = len(srcDocument.links)
    baseLinkIndexLen = len(baseDocument.links)
    stats["potentialMatchingLinksSetSize"] = min(baseLinkIndexLen,srcLinkIndexLen)
    if SHOW_STATUS:
        print 'Matching links between documents' + ("..." if CPU_COUNT == 1 else (" (using " + str(CPU_COUNT) + " threads)..."))
    nextIndex = 0
    finishedJobs = 0
    timemarker = time.time()
    global jobQueue
    jobQueue = []
    # bootstrap the job queue
    if baseLinkIndexLen > 0:
        jobQueue.append(LocalYieldingJob(baseDocument, nextIndex, srcDocument))
        nextIndex += 1
    while len(jobQueue) < CPU_COUNT and nextIndex < baseLinkIndexLen:
        jobQueue.append(BackgroundContinuousJob(baseDocument, nextIndex, srcDocument))
        nextIndex += 1
    while finishedJobs < baseLinkIndexLen: # this loop terminates after all base links are matched against all src links
        # review job queue:
        # * manage/update any finished jobs
        # * create new jobs to fill any vacancies
        # * resume any paused jobs
        # time check and report
        for i in xrange(0, len(jobQueue)):
            job = jobQueue[i]
            if job.hasResults:
                job.hasResults = False # avoid dropping in here a second time for this job
                # matches are 1:1 -- avoid collisions in matched results
                actualBaseMatchIndex = srcDocument.links[job.bestSrcIndex].matchIndex
                if job.matched and actualBaseMatchIndex != -1: # will trade one job for another, hense finishedJobs not incremented here...
                    # while multi-threaded, it is possible two (or more) threads will find the same matching result.
                    # This conflict is resolved by only accepting the result which would have logicaly found it
                    # first.
                    if actualBaseMatchIndex < job.baseIndex:
                        # this job's result is not valid (earlier match found is accepted); restart this job
                        job.replace(job.baseIndex, (job.bestSrcIndex + 1) % srcLinkIndexLen)
                    else: # existing (later) match is not valid (this match is accpeted); restart the errant "later" job
                        undoJobDetails(actualBaseMatchIndex, job, stats)
                        transferJobDetails(job, stats)
                        job.replace(actualBaseMatchIndex, (job.bestSrcIndex + 1) % srcLinkIndexLen)
                else:
                    finishedJobs += 1
                    transferJobDetails(job, stats) # update the base and src documents with the info from the job, including stats...
                    if nextIndex < baseLinkIndexLen:
                        job.replace(nextIndex, nextIndex % srcLinkIndexLen) # replace it with a new job
                        nextIndex += 1
            elif not job.isRunning:
                job.start()
        if SHOW_STATUS and (time.time() - timemarker) > 10: # in seconds
            timemarker = time.time()
            print percentComplete(finishedJobs, baseLinkIndexLen) + "\r",
    jobQueue = None # done with it.
    # Review any un-matched links and check for external non-matched..
    if SHOW_STATUS:
        print 'Finishing up...'
    for i in xrange(srcLinkIndexLen):
        srcElem = srcDocument.links[i]
        if not srcElem._matched and check4External(srcElem):
            srcElem.status = "non-matched-external"
    return (baseDocument, srcDocument)

def transferJobDetails(job, stats):
    baseElem = job.baseElem
    baseElem.status = job.baseStatus
    baseElem.matchIndex = job.bestSrcIndex
    baseElem.matchRatio = job.bestMatchRatio
    baseElem.correctRatio = job.correctRatio
    # below MODIFIES source link element objects WHILE other threads may be reading the data!!
    if job.matched:
        srcElem = job.srcDoc.links[job.bestSrcIndex]
        # NOTE: Previously the entire source link array was modified with updated "best index" and "best ratio" data.
        #        With the new design, this would have race conditions with potentially multiple threads writing and
        #        overwriting these values, with potential inconsistencies in the data. For now, these values will
        #        not be included.
        srcElem._matched = True
        srcElem.status = job.srcStatus
        srcElem.matchIndex = baseElem.index
        srcElem.correctRatio = job.correctRatio
        # End unsafe cross-threaded writes
        stats["matchingLinksTotal"] += 1
        if job.baseStatus == "skipped" or job.srcStatus == "skipped":
            stats["potentialMatchingLinksSetSize"] -= 1
        elif job.baseStatus == "correct" or job.baseStatus == "correct-external":
            stats["correctLinksTotal"] += 1

def undoJobDetails(baseRevertIndex, job, stats):
    #This reverts the job's current base element and reverts any relevant stats. Does not change any src element details
    toRevertElem = job.baseDoc.links[baseRevertIndex]
    if job.matched:
        stats["matchingLinksTotal"] -= 1
        if toRevertElem.status == "skipped" or job.srcStatus == "skipped":
            stats["potentialMatchingLinksSetSize"] += 1
        if toRevertElem.status == "correct" or toRevertElem.status == "correct-external":
            stats["correctLinksTotal"] -= 1
    toRevertElem.resetMatchStatus()

MATCH_RATIO_THRESHOLD = 0.7

def check4Match(job, srcElem):
    if srcElem._matched:
        return False
    ratio = getRatio(job.matcher, getContextualText(srcElem))
    if ratio > MATCH_RATIO_THRESHOLD:
        job.matched = True # True and the following data applies:
        job.baseStatus = job.srcStatus = "matched"
        job.bestSrcIndex = srcElem.index
        job.bestMatchRatio = ratio # the match ratio
        return True
    if ratio > job.bestMatchRatio:
        job.bestMatchRatio = ratio
        job.bestSrcIndex = srcElem.index
    return False

IGNORE_LIST = {}

# Only called after a pair of links has been matched. This "upgrades" the match (if possible) to an
# additional state: skipped, correct, correct-external, broken, or the [non-upgrade] matched-external.
def check4Correct(job, srcElem):
    if job.baseElem.href in IGNORE_LIST or srcElem.href in IGNORE_LIST:
        if job.baseElem.href in IGNORE_LIST:
            job.baseStatus = "skipped"
        if srcElem.href in IGNORE_LIST:
            job.srcStatus = "skipped"
        return
    isBaseHrefExternal = check4External(job.baseElem)
    isSrcHrefExternal = check4External(srcElem)
    if isBaseHrefExternal or isSrcHrefExternal:
        if isBaseHrefExternal and isSrcHrefExternal:
            if job.baseElem.href == srcElem.href:
                job.baseStatus = job.srcStatus = "correct-external"
                job.correctRatio = 1.0
            else:
                job.baseStatus = job.srcStatus = "matched-external"
        elif isBaseHrefExternal:
            job.baseStatus = "matched-external"
        else:
            job.srcStatus = "matched-external"
        return
    baseDest = job.baseDoc.getElementById(getLinkTarget(job.baseElem.href))
    srcDest = job.srcDoc.getElementById(getLinkTarget(srcElem.href))
    if baseDest == None or srcDest == None:
        if baseDest == None:
            job.baseStatus = "broken"
        if srcDest == None:
            job.srcStatus = "broken"
        return
    destCmpRatio = getAndCompareRatio(baseDest, srcDest)
    job.correctRatio = destCmpRatio
    if destCmpRatio > MATCH_RATIO_THRESHOLD:
        job.baseStatus = job.srcStatus = "correct"

def getAndCompareRatio(elem1, elem2):
    text1 = getContextualText(elem1)
    text2 = getContextualText(elem2)
    return compareRatio(text1, text2)

def compareRatio(baseText, srcText):
    matcher = SequenceMatcher(lambda n: n in ' \t')
    matcher.sequence2Text = baseText
    matcher.set_seq2(matcher.sequence2Text)
    return getRatio(matcher, srcText)

def getRatio(preConfiguredMatcher, sequence1Text):
    preConfiguredMatcher.set_seq1(sequence1Text) # fast(er) path, but is not commutative, so need to try both directions sometimes...
    ratio = preConfiguredMatcher.quick_ratio() #an upper-bound on the threshold
    if ratio >= (MATCH_RATIO_THRESHOLD - 0.25):
        ratio = preConfiguredMatcher.ratio()
    if ratio < MATCH_RATIO_THRESHOLD: # Try it the other way (python docs imply monotonically increasing compare, so not commutative)
        otherMatcher = SequenceMatcher(lambda x: x in ' \t', preConfiguredMatcher.sequence2Text, sequence1Text)
        ratioBackward = otherMatcher.quick_ratio()
        if ratioBackward >= (MATCH_RATIO_THRESHOLD - 0.25):
            ratioBackward = otherMatcher.ratio()
        ratio = max(ratio, ratioBackward)
    return ratio

HALF_WORD_COUNT = 10
    
# get HALF_WORD_COUNT words (or less if only less is available) in the indicated direction
def getDirectionalContextualWords(elem, isBeforeText):
    textCount = HALF_CONTEXT_MIN # should be enough, but if not, grow this variable.
    wordCount = 0
    #since lead or tail text may cut off a word (in the middle of a whole word), ask for one more word than needed and drop the potential half-word)
    while wordCount < HALF_WORD_COUNT + 1: # Should loop only once in typical cases...
        text, noMoreTextAvailable = getDirectionalContextualText(elem, isBeforeText, textCount)
        splitArray = re.split('\W+', text)
        headPos = 0
        tailPos = len(splitArray)
        # discount empty matches at the beginning/end of the array (the nature of 're.split')
        if tailPos > 0 and splitArray[0] == "":
            headPos = 1
        if tailPos > 1 and splitArray[-1] == "":
            tailPos = -1
        splitArray = splitArray[headPos:tailPos]
        if noMoreTextAvailable and len(splitArray) < HALF_WORD_COUNT: # There just isn't any more text; Call it good enough.
            if isBeforeText:
                return [word.lower() for word in splitArray[1:]] #drop the leading word, which is likely cut-off.
            else:
                return [word.lower() for word in splitArray[:-1]] #drop the trailing word, which is likely cut-off.
        wordCount = len(splitArray)
        textCount += 120 # growth factor on retry
    # word count met or exceeded HALF_WORD_COUNT threshold; trim and return
    if isBeforeText: #use list comprehension to lowercase each word in the list.
        return [word.lower() for word in splitArray[-HALF_WORD_COUNT:]] #back HALF_WORD_COUNT from the end, to the end.
    else:
        return [word.lower() for word in splitArray[:HALF_WORD_COUNT]] # 0 to HALF_WORD_COUNT (exclusive)
    
HALF_CONTEXT_MIN = 110 # Tuned using (W3C HTML spec text)

def getContextualText(elem):
    if elem._cachedContextualText != None:
        return elem._cachedContextualText
    combinedTextBefore, nomore = getDirectionalContextualText(elem, True, 150)
    combinedTextAfter, nomore = getDirectionalContextualText(elem, False, 150)
    # Note: this may be called from multiple threads. The contextual text is static and doesn't
    # mutate, so a race condition would only affect the timing of when this caching happens on the
    # element (not the value).
    elem._cachedContextualText = combinedTextBefore + combinedTextAfter
    return elem._cachedContextualText

# Returns a tuple of the requested text and a flag indicating whether more text is available to process.
def getDirectionalContextualText(elem, isBeforeText, characterLimit):
    text = ''
    count = 0
    runner = elem
    while count < characterLimit and runner != None:
        if isinstance(runner, TextNode):
            if isBeforeText:
                text = runner.textContent + text
            else: #after text
                text += runner.textContent
            count += len(runner.textContent)
        runner = runner.prev if isBeforeText else runner.next
    noMoreTextAvailable = (runner == None and count < characterLimit) # not enough characters accumulated!
    if isBeforeText:
        return text[-characterLimit:], noMoreTextAvailable
    else:
        return text[:characterLimit], noMoreTextAvailable

def check4External(link):
    if link.href[0:1] != '#':
        return True
    return False

def getLinkTarget(href):
    return urllib.unquote(href[1:])

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

def runTests(stats):
    global SHOW_STATUS #intend to modify a global variable.
    oldShowStatus = SHOW_STATUS
    SHOW_STATUS = False
    IGNORE_LIST['http://test/test/test.com'] = True

    # test 1
    parser = LinkAndTextHTMLParser()
    doc = parser.parse("<hello/><there id ='foo' /></there></hello>");
    assert doc.droppedTags == 1, "test1: expected only one dropped tag"
    assert doc.start.id == 'foo', "test1: expected 1st retained element to have id 'foo'"
    assert doc.start.next == None, "test1: element initialized correctly"
    assert doc.getElementById('foo') == doc.start, "test1: document can search for an element by id"
    assert doc.getElementById('foo2') == None, "test1: document fails to retrieve non-existant id"
    assert len(doc.links) == 0, "test1: no links were found"
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

    # (new) test 8 - unfortunate SequenceMatcher non-cummutative property on ratio computation...
    textA = "Top: if you're comparing lines as sequences of characters, and don't want to synch up on blanks or hard <a href='#test'>tabs. The optional arguments a and b are sequences to be compared; both default to empty strings. The elements of both sequences must be hashable. The stuff should match."
    textB = "Top: if you are comparing a line as sequences of characters, and don't want to synch up on blanks or hard <a href='#test'>tabs. The optional arguments a and b are sequences to be compared; both will default to empty strings. The elements of both sequences must be hashable thing. Otherwise bad."
    matcher = SequenceMatcher(lambda x: x in ' \t', textA, textB)
    ratioA = matcher.ratio()
    matcher.set_seqs(textB, textA)
    ratioB = matcher.ratio()
    istrue(ratioA == ratioB, False, "test8: ratio computation is not commutative -- both ends must be compared.")
    # getRatio corrects this by checking both dirctions and taking max()
    istrue(compareRatio(textA, textB), compareRatio(textB, textA), "test8: linkdiff compensates for lack of commutative comparisons.")

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
    doc, doc2 = diffLinks(parseTextToDocument(markup1, ""), parseTextToDocument(markup2, ""), stats)
    istrue(len(doc.links), 6, "test9: parsing validation-- 6 links in markup1")
    istrue(len(doc2.links), 6, "test9: parsing validation-- 6 links in markup2")
    istrue(doc.links[0].status, "broken", "test9: link matching validation: link is broken")
    istrue(doc.links[0].matchIndex, 0, "test9: link matching validation: matched at 0")
    istrue(doc2.links[doc.links[0].matchIndex].href, "#top", "test9: correct link (0) matched in source doc")
    istrue(doc.links[0].matchRatio > 0.97, True, "test9: link matching validation: Ratio is 0.97333-ish")
    istrue(doc.links[0].correctRatio, 0.0, "test9: link matching validation: default value for correctRatio not-correct")
    istrue(doc.links[1].status, "skipped", "test9: link matching validation: link is matched & skipped")
    istrue(doc.links[1].matchIndex, 1, "test9: link matching validation: matched at 1")
    istrue(doc2.links[doc.links[1].matchIndex].href, "http://test/test/test.com", "test9: correct link (1) matched in source doc")
    istrue(doc.links[1].matchRatio > 0.97, True, "test9: link matching validation: Ratio is 0.9741.")
    istrue(doc.links[1].correctRatio, 0.0, "test9: link matching validation: not correct--0 ratio")
    istrue(doc.links[2].status, "correct-external", "test9: link matching validation: link is correct, but external")
    istrue(doc.links[2].matchIndex, 2, "test9: link matching validation: matched at 2")
    istrue(doc2.links[doc.links[2].matchIndex].href, "http://external/comparing", "test9: correct link (2) matched in source doc")
    istrue(doc.links[2].matchRatio > 0.97, True, "test9: link matching validation: Ratio is 0.97885-ish")
    istrue(doc.links[2].correctRatio, 1.0, "test9: link matching validation: external link is 100% correct/same")
    istrue(doc.links[3].status, "correct", "test9: link matching validation: link is correct" + " got: " + doc.links[3].status + " ratio: " + str(doc.links[3].correctRatio))
    istrue(doc.links[3].matchIndex, 3, "test9: link matching validation: matched at 3")
    istrue(doc2.links[doc.links[3].matchIndex].href, "#sync", "test9: correct link (2) matched in source doc")
    istrue(doc.links[3].matchRatio > 0.88, True, "test9: link matching validation: Ratio is approx 0.8815")
    istrue(doc.links[3].correctRatio > 0.89, True, "test9: link matching validation: Correctness matching ratio is approx 0.894")
    istrue(doc.links[4].status, "non-matched", "test9: link matching validation: link is not matched")
    istrue(doc.links[4].matchIndex, 4, "test9: link matching validation: failed to match--all broken links checked, index set to best index (4)")
    istrue(doc.links[4].matchRatio < 0.36, True, "test9: link matching validation: Match ratio is too low to match, approx 0.359")
    istrue(doc.links[4].correctRatio, 0.0, "test9: link matching validation: un-matched correctRatio is 0.0")
    istrue(doc.links[5].status, "non-matched-external", "test9: link matching validation: link is not matched and external")
    istrue(doc.links[5].matchIndex, 4, "test9: link matching validation: matched at 4")
    istrue(doc.links[5].matchRatio < 0.47, True, "test9: link matching validation: not matched, low ratio (0.465)")
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
    doc, doc2 = diffLinks(parseTextToDocument(markup1, ""), parseTextToDocument(markup2, ""), stats)
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
    istrue(doc.links[1].correctRatio < 0.3, True, "test10: link matching validation: not correct--0.293 ratio")
    #dumpDocument(doc, True)

    # test 11 - href's with percent-encoding... (one-way, works for hrefs, not for targets)
    # note, Chrome 53 stable: tries to match link targets using both the pre-decoded text as well as the post-decoded text...Firefox/Edge do not do this, so this tool will not either.
    markup1 = '<p id="first()">first target</p><a href="#last()">goto last</a><a href="#last%28%29">alternate last</a>. This is some content. And here is some links: <a href="#first%28%29">goto first</a><p id="last%28%29">last target</p>'
    doc, doc2 = diffLinks(parseTextToDocument(markup1, ""), parseTextToDocument(markup1, ""), stats)
    istrue(doc.links[0].href, "#last()", "test11: no fancy escaping done to these characters by the HTMLParser implementation.")
    istrue(doc.links[0].status, "broken", "test11: percent-encoded attribute values in id are not converted to match.")
    istrue(doc.links[1].href, "#last%28%29", "test11: no fancy escaping done to percent-encoded characters by the HTMLParser implementation.")
    istrue(doc.links[1].status, "broken", "test11: href values are always decoded before checking for literal matching ids (see note on Chrome above)")
    istrue(doc.links[2].status, "correct", "test11: percent-encoded attribute values in hrefs are decoded to match.")
    #dumpDocument(doc, True)

    # test 12 - new indexing technique
    markup1 =  "<span id=matched>One</span> of the common, difficult to figure-out problems in the \n"
    markup1 += "current HTML spec is whether links are 'correct'. Not 'correct' as in syntax or as \n"
    #                                                                                  -10      -9
    markup1 += "opposite to broken links, but rather that the link in question goes to the semantically\n"
    #             -8      -7  -6  -5  -4  -3   -2    -1                                     1
    markup1 += "correct place in the Spec or other linked <a href='http://external/place1'>spec</a>. \n"
    #                2        3   4    5     6    7   8     9      10
    markup1 += "Correctness, in this sense, can only be determined by comparing \n"
    markup1 += "the links to a canonical 'correct' source. In the case of the W3C HTML spec, the \n"
    markup1 += "source used for determining correctness is the WHATWG version of the spec."
    doc = parseTextToDocument(markup1, "")
    #dumpDocument(doc, True)
    # TODO: Check how often 200 characters is too little--find the right balance for perf...
    resultWordList = getDirectionalContextualWords(doc.links[0], True)
    assert len(resultWordList) == HALF_WORD_COUNT, "test12: getDirectionalContextualWords returns "+str(HALF_WORD_COUNT)+" items from front of link"
    testList = ['the', 'semantically', 'correct', 'place', 'in', 'the', 'spec', 'or', 'other', 'linked']
    for i in xrange(len(testList)): 
        assert testList[i] == resultWordList[i], "test12: validating expected words before link"
    resultWordList = getDirectionalContextualWords(doc.links[0], False)
    assert len(resultWordList) == HALF_WORD_COUNT, "test12: getDirectionalContextualWords returns "+str(HALF_WORD_COUNT)+" items from back of link"
    testList = ['spec', 'correctness', 'in', 'this', 'sense', 'can', 'only', 'be', 'determined', 'by']
    for i in xrange(len(testList)): 
        assert testList[i] == resultWordList[i], "test12: validating expected words after link"
    buildIndex(doc, "")
    assert len(doc.index.keys()) == 14, "test12: total number of unique words indexed is 14 (others were in the too common list"
    testList = ['correct', 'be', 'linked', 'correctness', 'by', 'this', 'only', 'other', 'place', 'can', 'sense', 'semantically', 'determined', 'or']
    for word in doc.index.keys():
        assert word in testList, "test12: only expected words are in the index"
        assert doc.index[word][0] == 1, "test12: indexed words all have an initial occurance count of 1"
        assert doc.index[word][1] == 0, "test12: words are all found in first link"
        del testList[testList.index(word)]
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
    print "  their respective documents. The output is a JSON structure of the diff results."
    print ""
    print "Usage:"
    print ""
    print "  linkdiff [flags] <baseline html file> <source html file>"
    print ""
    print "    The baseline and source files may be paths to the respective files on disk, or URLs."
    print "    The only supported protocols for URLs are 'http' and 'https'; any other protocol will"
    print "    be interpreted as a local file path."
    print ""
    print "Flags:"
    print ""
    print "  -ratio <value between 0 and 1>"
    print ""
    print "    Example: linkdiff -ratio 0.9 baseline_doc.html source_doc.html"
    print ""
    print "      Overrides the default ratio used for verifying that a link is in the same place in"
    print "      both specs, and that the hyperlink's targets are in the same relative place. A low"
    print "      ratio (e.g., 0.25 or 25%) is more permissive in that only 25% of the relative surrounding"
    print "      content must be the same to be considered a match. A higher ratio (e.g., 0.9 or 90%) is"
    print "      more strict. The default (if the flag is not supplied) is 0.7 or 70%."
    print ""
    print "  -ignorelist <ignorelist_file>"
    print ""
    print "    Example: linkdiff -ignorelist ignore_list.json baseline_doc.html source_doc.html"
    print ""
    print "      The ignore list is a file containing a JSON object with a single property named"
    print "      'ignoreList' whose value is an array of strings. The strings should contain the absolute"
    print "      or relative URLs to skip/ignore during link verification. String matching is used to"
    print "      apply the strings to href values, so exact matches are required. The ignore list applies"
    print "      to both baseline and source html files"
    print ""
    print "  -statsonly"
    print ""
    print "    Example: linkdiff -statsonly http://location/of/baseline ../source/doc/location.htm"
    print ""
    print "      The JSON output is limited to the statistical values from the processing results. The"
    print "      detailed link report for both baseline and source documents is omitted."
    print ""
    print "  -v"
    print ""
    print "    Example: linkdiff -v baseline_doc.html source_doc.html"
    print ""
    print "      Shows verbose status messages during processing. Useful for monitoring the progress"
    print "      of the tool."
    print ""
    print "  -threads <value greater than 1>"
    print ""
    print "    Example: linkdiff -threads 1 baseline.html http://source.html"
    print "    Example: linkdiff -threads 16 baseline.html http://source.html"
    print ""
    print "      The first examples disables any multi-threading. Only one thread (the main thread)"
    print "      is used to perform the diff. May be more efficient for comparing documents with small"
    print "      numbers of links. The second example overrides the default to use 16 threads (15 background"
    print "      threads and the main thread) to perform the diff. Where this value exceeds the number of"
    print "      threads available on the system, your mileage may very. The default value is detected from"
    print "      the OS's number of available CPUs."
    print ""
    print "  -runtests"
    print ""
    print "    Example: linkdiff -runtests"
    print ""
    print "      When this flag is used, the <baseline html file> and <source html file> input values"
    print "      are not required. This flag runs the self-tests to ensure the code is working as expected"
    print ""

def dumpJSONResults(baseDoc, srcDoc, stats, showAllStats):
    if SHOW_STATUS:
        print "JSON output:"
        print ""
    print "{"
    print '  "ratioThreshold": ' + str(stats["ratioThreshold"]) + ","
    print '  "matchingLinksTotal": ' + str(stats["matchingLinksTotal"]) + ","
    print '  "correctLinksTotal": ' + str(stats["correctLinksTotal"]) + ","
    print '  "potentialMatchingLinksSetSize": ' + str(stats["potentialMatchingLinksSetSize"]) + ","
    print '  "percentMatched": ' + str(float(stats["matchingLinksTotal"]) / float(stats["potentialMatchingLinksSetSize"]))[:5] + ","
    print '  "percentCorrect": ' + str(float(stats["correctLinksTotal"]) / float(stats["potentialMatchingLinksSetSize"]))[:5] + ","
    print '  "baselineDoc": {'
    baseLinkTotal = len(baseDoc.links)
    print '    "linksTotal": ' + str(baseLinkTotal) + ","
    print '    "nonMatchedTotal": ' + str(baseLinkTotal - stats["matchingLinksTotal"]) + ("," if showAllStats else "")
    if showAllStats:
        print '    "linkIndex": [ '
        for link in baseDoc.links:
            print '      ' + str(link) + ("," if link.index < (baseLinkTotal-1) else "")
        print '    ]'
    print '  },'
    print '  "sourceDoc": {'
    srcLinkTotal = len(srcDoc.links)
    print '    "linksTotal": ' + str(srcLinkTotal) + ","
    print '    "nonMatchedTotal": ' + str(srcLinkTotal - stats["matchingLinksTotal"]) + ("," if showAllStats else "")
    if showAllStats:
        print '    "linkIndex": [ '
        for link in srcDoc.links:
            print '      ' + str(link) + ("," if link.index < (srcLinkTotal-1) else "")
        print '    ]'
    print '  }'
    print "}"

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

def setThreads(newThreadCount):
    global CPU_COUNT
    if newThreadCount == None:
        return
    newThreadCount = max(int(newThreadCount, 10), 1)
    CPU_COUNT = newThreadCount
    if SHOW_STATUS:
        print "Using custom thread count: " + str(CPU_COUNT)

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

def showStatus():
    global SHOW_STATUS
    SHOW_STATUS = True

def loadURL(url):
    try:
        if SHOW_STATUS:
            print "Getting '" + url + "' from the network..."
        urlhandle = urllib.urlopen(url)
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

def baseLineProcessEntryPoint(fileToLoad, globalState):
    # Set the "globals" for this process
    global SHOW_STATUS
    global MATCH_RATIO_THRESHOLD
    global IGNORE_LIST
    global CPU_COUNT
    SHOW_STATUS = globalState.showStatus
    MATCH_RATIO_THRESHOLD = globalState.matchRatioThreshold
    IGNORE_LIST = globalState.ignoreList
    CPU_COUNT = globalState.cpuCount
    # Load the document...
    baseDocText = loadDocumentText(fileToLoad)
    if baseDocText == None:
        globalState.baselineManagerError = True
        return
    # Parse the baseline document...
    baselineDoc = parseTextToDocument(baseDocText, 'Parsing baseline document...')
    buildIndex(sourceDoc, 'Indexing baseline document...')
    
    return
        
def processCmdParams():
    stats = {}
    stats["ratioThreshold"] = MATCH_RATIO_THRESHOLD
    stats["correctLinksTotal"] = 0
    if len(sys.argv) == 1:
        return cmdhelp()
    if "-runtests" in sys.argv:
        return runTests(stats)
    expectedArgs = 3
    showAllStats = True
    if "-v" in sys.argv:
        showStatus()
        expectedArgs += 1
    if "-statsonly" in sys.argv:
        showAllStats = False
        expectedArgs += 1
    if "-ratio" in sys.argv:
        setRatio(getFlagValue("-ratio"))
        expectedArgs += 2
    if "-threads" in sys.argv:
        setThreads(getFlagValue("-threads"))
        expectedArgs += 2
    if "-ignorelist" in sys.argv:
        setIgnoreList(getFlagValue("-ignorelist"))
        expectedArgs += 2
    if len(sys.argv) < expectedArgs:
        print "Usage error: <baseline_doc.html> and <source_doc.html> parameters required."
        return

    processManager = Manager()
    globalSharedState = processManager.Namespace()
    globalSharedState.baselineManagerError = False
    globalSharedState.showStatus = SHOW_STATUS
    globalSharedState.matchRatioThreshold = MATCH_RATIO_THRESHOLD
    globalSharedState.ignoreList = IGNORE_LIST
    globalSharedState.cpuCount = CPU_COUNT
    
    # Load and process baseline file in a separate Process
    p = Process(target=baseLineProcessEntryPoint, args=(sys.argv[expectedArgs-2], globalSharedState), name="linkdiff_baseline_processor")
    p.start()
    # Load sourceDoc (in this process)
    sourceDocText = loadDocumentText(sys.argv[expectedArgs-1])
    if sourceDocText == None or globalSharedState.baselineManagerError:
        return
    sourceDoc = parseTextToDocument(sourceDocText, 'Parsing source document...')
    s_time = time.time()
    buildIndex(sourceDoc, 'Indexing source document...')
    print str(time.time() - s_time) + ' seconds elapsed for indexing...'
    # Sync point
    p.join()
    if globalSharedState.baselineManagerError:
        return
    print "success!"
    
    #baseDoc, sourceDoc = diffLinks(baseDocText, sourceDocText, stats)
    #dumpJSONResults(baseDoc, sourceDoc, stats, showAllStats)

# Only the main process should execute this (spawned processes will skip it)
if __name__ == '__main__':
    processCmdParams()
