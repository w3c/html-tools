import os, sys
import config, bs, boilerplate, parser_microsyntax
from StringIO import StringIO
from anolislib import generator, utils

def invoked_incorrectly():
    specs = config.load_config().keys()
    sys.stderr.write("Usage: python %s [%s]\n" % (sys.argv[0],'|'.join(specs)))
    exit()

def main(spec, spec_dir, branch="master"):
    conf = None
    try:
        conf = config.load_config()[spec]
    except KeyError:
        invoked_incorrectly()

    if 'select' in conf:
        select = conf['select']
    else:
        select = spec

    try:
        if not spec_dir:
            if conf.get("bareOutput", False):
                spec_dir = conf["output"]
            else:
                spec_dir = os.path.join(conf["output"], spec)
    except KeyError:
        sys.stderr.write("error: Must specify output directory for %s! \
Check default-config.json.\n" % spec)
        exit()

    cur_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(conf["path"])

    print "parsing"
    source = open('source')
    after_microsyntax = StringIO()
    parser_microsyntax.main(source, after_microsyntax)
    after_microsyntax.seek(0)
    succint = StringIO()
    bs.main(after_microsyntax, succint)

    succint.seek(0)
    filtered = StringIO()
    try:
        boilerplate.main(succint, filtered, select, branch)
    except IOError:
        sys.stderr.write("error: Problem loading boilerplate for %s. \
Are you on the correct branch?\n" % spec)
        exit()
    succint.close()

    # See http://hg.gsnedders.com/anolis/file/tip/anolis
    opts = {
      'allow_duplicate_dfns': True,
      'disable': None,
      'escape_lt_in_attrs': False,
      'escape_rcdata': False,
      'force_html4_id': False,
      'indent_char': u' ',
      'inject_meta_charset': False,
      'max_depth': 6,
      'min_depth': 2,
      'minimize_boolean_attributes': False,
      'newline_char': u'\n',
      'omit_optional_tags': False,
      'output_encoding': 'utf-8',
      'parser': 'html5lib',
      'processes': set(['toc', 'xref', 'sub']),
      'profile': False,
      'quote_attr_values': True,
      'serializer': 'html5lib',
      'space_before_trailing_solidus': False,
      'strip_whitespace': None,
      'use_best_quote_char': False,
      'use_trailing_solidus': False,
      'w3c_compat_class_toc': False,
      'w3c_compat_crazy_substitutions': False,
      'w3c_compat_substitutions': False,
      'w3c_compat': True,
      'w3c_compat_xref_a_placement': False,
      'w3c_compat_xref_elements': False,
      'w3c_compat_xref_normalization': False,
    }
    if "anolis" in conf:
        opts.update(conf["anolis"])

    if spec == "srcset":
        import html5lib

        print 'munging (before anolis)'

        filtered.seek(0)
        pre_anolis_buffer = StringIO()

        # Parse
        parser = html5lib.html5parser.HTMLParser(tree = html5lib.treebuilders.getTreeBuilder('lxml'))
        tree = parser.parse(filtered, encoding='utf-8')

        # Move introduction above conformance requirements
        introduction = tree.findall("//*[@id='introduction']")[0]
        intro_ps = introduction.xpath("following-sibling::*")
        target = tree.findall("//*[@id='conformance-requirements']")[0]
        target.addprevious(introduction)
        target = introduction
        target.addnext(intro_ps[2])
        target.addnext(intro_ps[1])
        target.addnext(intro_ps[0])

        # Serialize
        tokens = html5lib.treewalkers.getTreeWalker('lxml')(tree)
        serializer = html5lib.serializer.HTMLSerializer(quote_attr_values=True, inject_meta_charset=False)
        for text in serializer.serialize(tokens, encoding='utf-8'):
            pre_anolis_buffer.write(text)

        filtered = pre_anolis_buffer

    print 'indexing'
    filtered.seek(0)
    tree = generator.fromFile(filtered, **opts)
    filtered.close()

    # fixup nested dd's and dt's produced by lxml
    for dd in tree.findall('//dd/dd'):
        if list(dd) or dd.text.strip():
            dd.getparent().addnext(dd)
        else:
            dd.getparent().remove(dd)
    for dt in tree.findall('//dt/dt'):
        if list(dt) or dt.text.strip():
            dt.getparent().addnext(dt)
        else:
            dt.getparent().remove(dt)

    if spec == "microdata":
        print 'munging'
        # get the h3 for the misplaced section (it has no container)
        section = tree.xpath("//h3[@id = 'htmlpropertiescollection']")[0]
        # then get all of its following siblings that have the h2 for the next section as 
        # a following sibling themselves. Yeah, XPath doesn't suck.
        section_content = section.xpath("following-sibling::*[following-sibling::h2[@id='introduction']]")
        target = tree.xpath("//h2[@id = 'converting-html-to-other-formats']")[0].getparent()
        target.addprevious(section)
        for el in section_content: target.addprevious(el)
        section.xpath("span")[0].text = "6.1 "
        # move the toc as well
        link = tree.xpath("//ol[@class='toc']//a[@href='#htmlpropertiescollection']")[0]
        link.xpath("span")[0].text = "6.1 "
        tree.xpath("//ol[@class='toc']/li[a[@href='#microdata-dom-api']]")[0].append(link.getparent().getparent())

    if spec == "srcset":
        print 'munging (after anolis)'
        # In the WHATWG spec, srcset="" is simply an aspect of
        # HTMLImageElement and not a separate feature. In order to keep
        # the HTML WG's srcset="" spec organized, we have to move some
        # things around in the final document.

        # Move "The srcset IDL attribute must reflect..."
        reflect_the_content_attribute = tree.findall("//div[@class='impl']")[0]
        target = tree.find("//div[@class='note']")
        target.addprevious(reflect_the_content_attribute)

        # Move "The IDL attribute complete must return true..."
        note_about_complete = tree.findall("//p[@class='note']")[5]
        p_otherwise = note_about_complete.xpath("preceding-sibling::p[position()=1]")[0]
        ul_conditions = p_otherwise.xpath("preceding-sibling::ul[position()=1]")[0]
        p_start = ul_conditions.xpath("preceding-sibling::p[position()=1]")[0]
        target.addnext(note_about_complete)
        target.addnext(p_otherwise)
        target.addnext(ul_conditions)
        target.addnext(p_start)

    try:
        os.makedirs(spec_dir)
    except:
        pass

    if spec == 'html':
        print 'cleaning'
        from glob import glob
        for name in glob("%s/*.html" % spec_dir):
            os.remove(name)

        output = StringIO()
    else:
        output = open("%s/Overview.html" % spec_dir, 'wb')

    generator.toFile(tree, output, **opts)

    if spec != 'html':
        output.close()
    else:
        value = output.getvalue()
        if "<!--INTERFACES-->\n" in value:
            print 'interfaces'
            from interface_index import interface_index
            output.seek(0)
            index = StringIO()
            interface_index(output, index)
            value = value.replace("<!--INTERFACES-->\n", index.getvalue(), 1)
            index.close()
        output = open("%s/single-page.html" % spec_dir, 'wb')
        output.write(value)
        output.close()
        value = ''

        print 'splitting'
        import spec_splitter
        spec_splitter.w3c = True
        spec_splitter.no_split_exceptions = conf.get("no_split_exceptions", False)
        spec_splitter.minimal_split_exceptions = conf.get("minimal_split_exceptions", False)
        spec_splitter.main("%s/single-page.html" % spec_dir, spec_dir)

        print 'entities'
        entities = open(os.path.join(cur_dir, "boilerplate/entities.inc"))
        json = open("%s/entities.json" % spec_dir, 'w')
        from entity_processor_json import entity_processor_json
        entity_processor_json(entities, json)
        entities.close()
        json.close()

    # copying dependencies
    def copy_dependencies (targets):
        import types
        if not isinstance(targets, types.ListType): targets = [targets]
        for target in targets:
            os.system("/bin/csh -i -c '/bin/cp -R %s %s'" % (os.path.join(conf["path"], target), spec_dir))

    print "copying"
    if spec == "html":
        copy_dependencies(["images", "fonts", "404/*", "switcher", "js"])
    elif spec == "2dcontext":
        copy_dependencies(["images", "fonts"])
    else:
        copy_dependencies("fonts")

    # fix the styling of the 404
    if spec == "html":
        link = tree.xpath("//link[starts-with(@href, 'http://www.w3.org/StyleSheets/TR/')]")[0].get("href")
        path = os.path.join(spec_dir, "404.html")
        with open(path) as data: html404 = data.read()
        html404 = html404.replace("http://www.w3.org/StyleSheets/TR/W3C-ED", link)
        with open(path, "w") as data: data.write(html404)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        invoked_incorrectly()
    spec = sys.argv[1]
    try:
        spec_dir = sys.argv[2]
    except IndexError:
        spec_dir = None
    try:
        branch = sys.argv[3]
    except IndexError:
        branch = None
    main(spec, spec_dir, branch)
