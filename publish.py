import os, sys
import bs, boilerplate
from StringIO import StringIO
from anolislib import generator, utils

if len(sys.argv)>1 and sys.argv[1] == 'html':
  select = 'w3c-html'
  spec = 'html'
elif len(sys.argv)>1 and sys.argv[1] == 'microdata':
  select = spec = 'microdata'
elif len(sys.argv)>1 and sys.argv[1] == '2dcontext':
  spec = select = '2dcontext'
else:
  sys.stderr.write("Usage: python %s [html|2dcontext|microdata]\n" % sys.argv[0])
  exit()

print 'parsing'
os.chdir(os.path.abspath(os.path.join(__file__, '../..')))
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

try:
  os.makedirs('output/%s' % spec)
except:
  pass

if spec == 'html':
  from glob import glob
  for name in glob('output/html/*.html'):
    os.remove(name)

  output = StringIO()
else:
  output = open('output/%s/Overview.html' % spec, 'wb')

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
  output = open('output/html/single-page.html', 'wb')
  output.write(value)
  output.close()
  value = ''

  print 'splitting'
  import spec_splitter
  spec_splitter.w3c = True
  spec_splitter.main('output/%s/single-page.html' % spec, 'output/%s' % spec)

  entities = open('boilerplate/entities.inc')
  json = open('output/html/entities.json', 'w')
  from entity_processor_json import entity_processor_json
  entity_processor_json(entities, json)
  entities.close()
  json.close()
