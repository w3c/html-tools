#!/usr/bin/python

import sys, re

def interface_index(input, output):
  definitions = {}
  inpre = False
  def_re = re.compile(r'(partial )?interface <(dfn|a) id=([^ >]*).*?>(.*)</\2>')
  for line in input.readlines():
    if '<pre class=idl>' in line: inpre = True
    if inpre:
      match = def_re.search(line)
      if match:
        partial, _, id, name = match.groups()
        if not name in definitions: definitions[name] = {}
        if partial:
          if not 'partial' in definitions[name]: 
            definitions[name]['partial'] = []
          definitions[name]['partial'].append(id)
        else:
          if 'primary' in definitions[name]:
            print >> sys.stderr, "duplicate interface definitions for %s" % name
            sys.exit(1)
          definitions[name]['primary'] = id
    if '</pre>' in line: inpre = False

  output.write("<ul>\n")
  for name in sorted(definitions.keys()):
    output.write(" <li><code>")
    if 'primary' in definitions[name]:
      output.write("<a href=#%s>%s</a>" % (definitions[name]['primary'], name))
    else:
      output.write(name)
    output.write("</code>")
    if 'partial' in definitions[name]:
      output.write(", <a href=#%s>partial" % definitions[name]['partial'][0])
      if len(definitions[name]['partial']) > 1: print " 1",
      output.write("</a>")
      for i in range(1, len(definitions[name]['partial'])):
        output.write(" <a href=#%s>%s</a>" % (definitions[name]['partial'][i], i))
    output.write("\n")
  output.write("</ul>\n")

if __name__ == '__main__':
  interface_index(sys.stdin, sys.stdout)
