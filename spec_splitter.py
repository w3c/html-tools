import sys, re, os
from lxml import etree # requires lxml 2.0
from copy import deepcopy

verbose = False
w3c = False
use_html5lib_parser = False
use_html5lib_serialiser = True
make_index_of_terms = False
no_split_exceptions = False
minimal_split_exceptions = False
in_semantics = False
in_semantics_seen_first = False

def main(input, output):
  global no_split_exceptions
  if use_html5lib_parser or use_html5lib_serialiser:
      import html5lib
      import html5lib.serializer
      import html5lib.treewalkers

  index_page = 'Overview'

  # The document is split on all <h2> elements, plus the following specific elements
  # (which were chosen to split any pages that were larger than about 100-200KB, and
  # may need to be adjusted as the spec changes):
  split_exceptions = [
      'the-a-element', 'the-abbr-element', 'the-address-element',
      'the-area-element', 'the-article-element', 'the-aside-element',
      'the-audio-element', 'the-b-element', 'the-base-element',
      'the-bdi-element', 'the-bdo-element', 'the-blockquote-element',
      'the-body-element', 'the-br-element', 'the-button-element',
      'the-canvas-element', 'the-caption-element', 'the-cite-element',
      'the-code-element', 'the-col-element', 'the-colgroup-element',
      'the-command-element', 'the-datalist-element', 'the-dd-element',
      'the-del-element', 'the-details-element', 'the-dfn-element',
      'the-dir-element', 'the-div-element', 'the-dl-element',
      'the-dt-element', 'the-em-element', 'the-embed-element',
      'the-fieldset-element', 'the-figcaption-element', 'the-figure-element',
      'the-footer-element', 'the-form-element',
      'the-h1-h2-h3-h4-h5-and-h6-elements', 'the-head-element',
      'the-header-element', 'the-hgroup-element', 'the-hr-element',
      'the-html-element', 'the-i-element', 'the-iframe-element',
      'the-img-element', 'the-input-element', 'the-ins-element',
      'the-kbd-element', 'the-keygen-element', 'the-label-element',
      'the-legend-element', 'the-li-element', 'the-link-element',
      'the-map-element', 'the-mark-element', 'the-menu-element',
      'the-meta-element', 'the-meter-element', 'the-nav-element',
      'the-noscript-element', 'the-object-element', 'the-ol-element',
      'the-optgroup-element', 'the-option-element', 'the-output-element',
      'the-p-element', 'the-param-element', 'the-pre-element',
      'the-progress-element', 'the-q-element', 'the-rp-element',
      'the-rt-element', 'the-ruby-element', 'the-s-element',
      'the-samp-element', 'the-script-element', 'the-section-element',
      'the-select-element', 'the-small-element', 'the-source-element',
      'the-span-element', 'the-strong-element', 'the-style-element',
      'the-sub-and-sup-elements', 'the-summary-element', 'the-table-element',
      'the-tbody-element', 'the-td-element', 'the-textarea-element',
      'the-tfoot-element', 'the-th-element', 'the-thead-element',
      'the-time-element', 'the-title-element', 'the-tr-element',
      'the-track-element', 'the-u-element', 'the-ul-element',
      'the-var-element', 'the-video-element', 'the-wbr-element',

      'styling',
      'usage-summary',
      'attributes-common-to-ins-and-del-elements',
      'edits-and-paragraphs',
      'edits-and-lists',
      'media-elements',
      'image-maps',
      'mathml',
      'svg-0',
      'dimension-attributes',
      'attributes-common-to-td-and-th-elements',
      'examples',
      'common-input-element-apis',

      'global-attributes',
      'element-definitions',
      'common-dom-interfaces',
      'namespaces',
      'requirements-relating-to-bidirectional-algorithm-formatting-characters',
      'wai-aria',
      'interactions-with-xpath-and-xslt',
      'headings-and-sections',

      'dynamic-markup-insertion',
      'common-microsyntaxes', 'urls', # <-- infrastructure
      'elements', 'content-models', 'apis-in-html-documents', # <-- dom

      'attributes-common-to-form-controls',
      'textFieldSelection',
      'constraints',
      'form-submission',

      'common-idioms-without-dedicated-elements',

      'scripting-1', 'sections', 'grouping-content', 'text-level-semantics', 'edits',
      'embedded-content-1', 'tabular-data',
      'forms', 'states-of-the-type-attribute', 'number-state', 'common-input-element-attributes', 'the-button-element', 'association-of-controls-and-forms',
      'interactive-elements', 'commands', # <-- semantics

      'predefined-vocabularies-0', 'converting-html-to-other-formats', # <-- microdata
      'origin-0', 'timers', 'offline', 'history', 'links', # <-- browsers
      'user-prompts',
      'system-state-and-capabilities',
      'dnd', # <-- editing
      'editing-apis',

      'parsing', 'tokenization', 'tree-construction', 'the-end', 'named-character-references', # <-- syntax
  ]
  if no_split_exceptions or minimal_split_exceptions: split_exceptions = []


  if verbose: print "Parsing..."

  # Parse document
  if use_html5lib_parser:
      parser = html5lib.html5parser.HTMLParser(tree = html5lib.treebuilders.getTreeBuilder('lxml'))
      doc = parser.parse(open(input), encoding='utf-8')
  else:
      parser = etree.HTMLParser(encoding='utf-8')
      doc = etree.parse(open(input), parser)

  if verbose: print "Splitting..."

  doctitle = doc.find('.//title').text

  if make_index_of_terms:
    # get all the nodes from the index of terms (if any) and save for later
    index_of_terms = doc.xpath("//*[@class='index-of-terms']//dl")

  # Extract the body from the source document
  original_body = doc.find('body')

  # Create an empty body, for the page content to be added into later
  default_body = etree.Element('body')
  if original_body.get('class'): default_body.set('class', original_body.get('class'))
  default_body.set('onload', 'fixBrokenLink();')
  original_body.getparent().replace(original_body, default_body)

  # Extract the header, so we can reuse it in every page
  header = original_body.find('.//*[@class="head"]')

  # Make a stripped-down version of it
  short_header = deepcopy(header)
  del short_header[4:]

  # Extract the items in the TOC (remembering their nesting depth)
  def extract_toc_items(items, ol, depth):
      for li in ol.iterchildren():
          for c in li.iterchildren():
              if c.tag == 'a':
                if c.get('href')[0] == '#':
                  items.append( (depth, c.get('href')[1:], c) )
              elif c.tag == 'ol':
                  extract_toc_items(items, c, depth+1)
  toc_items = []
  extract_toc_items(toc_items, original_body.find('.//ol[@class="toc"]'), 0)

  # Stuff for fixing up references:

  def get_page_filename(name):
      return '%s.html' % name

  # Finds all the ids and remembers which page they were on
  id_pages = {}
  def extract_ids(page, node):
      if node.get('id'):
          id_pages[node.get('id')] = page
      for e in node.findall('.//*[@id]'):
          id_pages[e.get('id')] = page

  # Updates all the href="#id" to point to page#id
  missing_warnings = set()
  def fix_refs(page, node):
      for e in node.findall('.//a[@href]'):
          if e.get('href')[0] == '#':
              id = e.get('href')[1:]
              if id in id_pages:
                  if id_pages[id] != page: # only do non-local links
                      e.set('href', '%s#%s' % (get_page_filename(id_pages[id]), id))
              else:
                  missing_warnings.add(id)

  def report_broken_refs():
      for id in sorted(missing_warnings):
          print "warning: can't find target for #%s" % id

  pages = [] # for saving all the output, so fix_refs can be called in a second pass

  # Iterator over the full spec's body contents
  child_iter = original_body.iterchildren()

  def add_class(e, cls):
      if e.get('class'):
          e.set('class', e.get('class') + ' ' + cls)
      else:
          e.set('class', cls)

  # Contents/intro page:

  page = deepcopy(doc)
  page_body = page.find('body')
  add_class(page_body, 'split index')

  # Keep copying stuff from the front of the source document into this
  # page, until we find the first heading that isn't class="no-toc"
  for e in child_iter:
      if e.getnext().tag == 'h2' and 'no-toc' not in (e.getnext().get('class') or '').split(' '):
          break
      page_body.append(e)

  pages.append( (index_page, page, 'Front cover') )

  # Section/subsection pages:

  def should_split(e):
      global in_semantics, in_semantics_seen_first
      if e.get("id") == "semantics":
          in_semantics = True
          return True
      if e.tag == 'h2':
          in_semantics = False
          return True
      if e.tag == "h3" and in_semantics and minimal_split_exceptions:
          if in_semantics_seen_first: return True
          in_semantics_seen_first = True
      if e.get('id') in split_exceptions: return True
      if e.tag == 'div' and e.get('class') == 'impl':
          c = e.getchildren()
          if len(c):
              if c[0].tag == 'h2': return True
              if c[0].tag == "h3" and in_semantics and minimal_split_exceptions: return True
              if c[0].get('id') in split_exceptions: return True
      return False

  def get_heading_text_and_id(e):
      if e.tag == 'div' and e.get('class') == 'impl':
          node = e.getchildren()[0]
      else:
          node = e
      title = re.sub('\s+', ' ', etree.tostring(node, method='text').strip())
      return title, node.get('id')

  for heading in child_iter:
      # Handle the heading for this section
      title, name = get_heading_text_and_id(heading)
      if name == index_page: name = 'section-%s' % name
      if verbose: print '  <%s> %s - %s' % (heading.tag, name, title)

      page = deepcopy(doc)
      page_body = page.find('body')
      add_class(page_body, 'split chapter')

      page.find('//title').text = title + u' \u2014 ' + doctitle

      # Add the header
      page_body.append(deepcopy(short_header))

      # Add the page heading
      page_body.append(deepcopy(heading))
      extract_ids(name, heading)

      # Keep copying stuff from the source, until we reach the end of the
      # document or find a header to split on
      e = heading
      while e.getnext() is not None and not should_split(e.getnext()):
          e = child_iter.next()
          extract_ids(name, e)
          page_body.append(deepcopy(e))

      pages.append( (name, page, title) )

  # Fix the links, and add some navigation:

  for i in range(len(pages)):
      name, doc, title = pages[i]

      fix_refs(name, doc)

      if name == index_page: continue # don't add nav links to the TOC page

      head = doc.find('head')

      nav = etree.Element('nav')
      nav.set('class', 'prev_next')
      nav.text = '\n   '
      nav.tail = '\n\n  '

      if i > 1:
          href = get_page_filename(pages[i-1][0])
          title = pages[i-1][2]
          a = etree.XML(u'<a href="%s">\u2190 %s</a>' % (href, title))
          a.tail = u' \u2013\n   '
          nav.append(a)
          link = etree.XML('<link href="%s" title="%s" rel="prev"/>' % (href, title))
          link.tail = '\n  '
          head.append(link)

      a = etree.XML('<a href="%s.html#contents">Table of contents</a>' % index_page)
      a.tail = '\n  '
      nav.append(a)
      link = etree.XML('<link href="%s.html#contents" title="Table of contents" rel="contents"/>' % index_page)
      link.tail = '\n  '
      head.append(link)

      if i != len(pages)-1:
          href = get_page_filename(pages[i+1][0])
          title = pages[i+1][2]
          a = etree.XML(u'<a href="%s">%s \u2192</a>' % (href, title))
          a.tail = '\n  '
          nav.append(a)
          a.getprevious().tail = u' \u2013\n   '
          link = etree.XML('<link href="%s" title="%s" rel="next"/>' % (href, title))
          link.tail = '\n  '
          head.append(link)

      # Add a subset of the TOC to each page:

      # Find the items that are on this page
      new_toc_items = [ (d, id, e) for (d, id, e) in toc_items if id_pages[id] == name ]
      if len(new_toc_items) > 1: # don't bother if there's only one item, since it looks silly
          # Construct the new toc <ol>
          new_toc = etree.XML(u'<ol class="toc"/>')
          cur_ol = new_toc
          cur_li = None
          cur_depth = 0
          # Add each item, reconstructing the nested <ol>s and <li>s to preserve
          # the nesting depth of each item
          for (d, id, e) in new_toc_items:
              while d > cur_depth:
                  if cur_li is None:
                      cur_li = etree.XML(u'<li/>')
                      cur_ol.append(cur_li)
                  cur_ol = etree.XML('<ol/>')
                  cur_li.append(cur_ol)
                  cur_li = None
                  cur_depth += 1
              while d < cur_depth:
                  cur_li = cur_ol.getparent()
                  cur_ol = cur_li.getparent()
                  cur_depth -= 1
              cur_li = etree.XML(u'<li/>')
              cur_li.append(deepcopy(e))
              cur_ol.append(cur_li)
          nav.append(new_toc)

      doc.find('body').insert(1, nav) # after the header

  if make_index_of_terms:
  # Write additional separate files for each term entry in the index of terms.
  # Each term entry should be a <dl> with an id attribute whose value is an id of
  # a <dfn>, with the string "_index" appended to it.
  # For now, the subdirectory for the files is hardcoded here as "index-of-terms".
    os.makedirs(os.path.join(output, "index-of-terms"))
    for term in index_of_terms:
    # the firstChild <dt> here is a name and link for the defining instance of
    # each index term; we don't need that in this context, so just remove it
        term.remove(term.find("./dt"))
        fix_refs('DUMMY', term)
        # we use the ID of the term as the base for the filename, minus the last six
        # characters ("_index")
        id = term.get("id")[:-6]
        f = open(os.path.join(output, "index-of-terms", id + ".html"), 'w')
        f.write(etree.tostring(term, pretty_print=True, method="html"))

  report_broken_refs()

  if verbose: print "Outputting..."

  # Output all the pages
  for name, doc, title in pages:
      f = open(os.path.join(output, get_page_filename(name)), 'w')
  #    f.write("<!doctype html>\n")
      if use_html5lib_serialiser:
          tokens = html5lib.treewalkers.getTreeWalker('lxml')(doc)
          serializer = html5lib.serializer.HTMLSerializer(quote_attr_values=True, inject_meta_charset=False)
          for text in serializer.serialize(tokens, encoding='us-ascii'):
            f.write(text)
      else:
          f.write(etree.tostring(doc, pretty_print=False, method="html"))

  # Generate the script to fix broken links
  f = open('%s/fragment-links.js' % (output), 'w')
  links = ','.join("'%s':'%s'" % (k.replace("\\", "\\\\").replace("'", "\\'"), v) for (k,v) in id_pages.items())
  f.write('var fragment_links = { ' + re.sub(r"([^\x20-\x7f])", lambda m: "\\u%04x" % ord(m.group(1)), links) + ' };\n')
  f.write("""
  var fragid = window.location.hash.substr(1);
  if (!fragid) { /* handle section-foo.html links from the old multipage version, and broken foo.html from the new version */
      var m = window.location.pathname.match(/\/(?:section-)?([\w\-]+)\.html/);
      if (m) fragid = m[1];
  }
  var page = fragment_links[fragid];
  if (page) {
      window.location.replace(page+'.html#'+fragid);
  }
  """)

  if verbose: print "Done."

if __name__ == '__main__':
  file_args = []
  verbose = True

  for arg in sys.argv[1:]:
      if arg == '--w3c':
          w3c = True
      elif arg == '-q' or arg == '--quiet':
          verbose = False
      elif arg == '--html5lib-parser':
          use_html5lib_parser = True
      elif arg == '--html5lib-serialiser':
          use_html5lib_serialiser = True
      elif arg == '--make-index-of-terms':
          make_index_of_terms = True
      else:
          file_args.append(arg)

  if verbose: print "HTML5 Spec Splitter"

  if len(file_args) != 2:
      print 'Run like "python spec-splitter.py [options] index multipage"'
      print '(The directory "multipage" must already exist)'
      print
      print 'Options:'
      print '  --w3c .................. use W3C variant instead of WHATWG'
      print '  --quiet ................ be less verbose in the output'
      print '  --html5lib-parser ...... use html5lib parser instead of lxml'
      print '  --html5lib-serialiser .. use html5lib serialiser instead of lxml'
      sys.exit()

  main(file_args)
