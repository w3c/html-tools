import os, sys
import config, bs, boilerplate
from StringIO import StringIO
from anolislib import generator, utils

def invoked_incorrectly():
  specs = config.load_config().keys()
  sys.stderr.write("Usage: python %s [%s]\n" % (sys.argv[0],'|'.join(specs)))
  exit()


def main(spec, spec_dir):
    conf = None
    try:
      conf = config.load_config()[spec]
    except KeyError:
      invoked_incorrectly()

    if 'select' in conf:
      select = conf['select']
    else:
      select = spec

    print "spec: %s\nselect: %s\nboilerplate: %s" % (spec, select, conf['boilerplate'])

    if not spec_dir: spec_dir = os.path.join(conf["output"], spec)

    print 'parsing'
    os.chdir(conf["path"])
    source = open('source')
    succint = StringIO()
    bs.main(source, succint)

    succint.seek(0)
    filtered = StringIO()
    boilerplate.main(succint, filtered, select)
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
        import lxml
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
        reflect_the_content_attribute = tree.findall("//div[@class='impl']")[1]
        target = tree.find("//div[@class='note']")
        target.addprevious(reflect_the_content_attribute)

    try:
      os.makedirs(spec_dir)
    except:
      pass

    if spec == 'html':
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

      entities = open(os.path.join(conf["path"], "boilerplate/entities.inc"))
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
            os.system("cp -R %s %s" % (os.path.join(conf["path"], target), spec_dir))

    print "copying"
    if spec == "html":
        copy_dependencies(["images", "fonts", "404/*"])
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
    main(spec, spec_dir)
