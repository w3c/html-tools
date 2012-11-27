import sys, config

def main(stdin, stdout, select='w3c-html'):
  import os, re
  spec = select
  if spec == "w3c-html": spec = "html"
  conf = config.load_config()[spec]
  os.chdir(config.rel_to_me(conf["path"], __file__))
  bp_dir = os.path.join(config.rel_to_me(conf["path"], __file__), "boilerplate")

  # select document
  header = open(os.path.join(bp_dir, conf["boilerplate"])).read()

  # remove instructions
  header = re.compile('<!-- .*? -->\n?', re.S).sub('', header)

  # capture variables
  vars = {}
  def vset(match): 
    vars[match.group(1)]=match.group(2)
    return ''
  header = re.sub('<!--SET (\w+)=(.*?)-->\n?', vset, header)

  # include nested boiler plate
  def boilerplate(match):
    name = match.group(1)
    if os.path.exists(os.path.join(bp_dir, name)):
      content = open(os.path.join(bp_dir, name)).read()
    else:
      content = match.group(0)
      sys.stderr.write("Missing file: %s\n" % name)

    # substitute variables
    content = re.sub('<!--INSERT (\w+)-->', lambda n: vars[n.group(1)], content)

    # use content as the replacement
    return content
  header = re.sub('<!--BOILERPLATE ([-.\w]+)-->', boilerplate, header)
  header = re.sub('<!--INSERT (\w+)-->', lambda n: vars[n.group(1)], header)

  source = stdin.read()
  source = re.compile('^.*?<!--START %s-->' % select, re.DOTALL).sub('', source)
  source = re.sub('<!--BOILERPLATE ([-.\w]+)-->', boilerplate, source)

  content =  header + source

  def adjust_headers(text, delta, pos, endpos=None):
    print "\tadjusting headers by %d from %d to %s" % (delta,
      pos, endpos if endpos is not None else "EOF")

    def adjust_header(match):
      slash = match.group(1)
      n = int(match.group(2)) - delta
      return "<%sh%d>" % (slash, n)

    headers = re.compile("<(/?)h([0-6])>", re.IGNORECASE)
    before = text[0:pos]
    if endpos is not None:
      between = text[pos:endpos]
      after = text[endpos:]
    else:
      between = text[pos:]
      after = ""
    return before + headers.sub(adjust_header, between) + after

  def process_fixup(content):
    print "fixup"
    current_position = 0
    adjustment = 0

    fixups = re.compile("<!--FIXUP %s ([+-])([0-9])-->" % select)

    fixup = fixups.search(content, current_position)
    while fixup is not None:
      if fixup.group(1) == '+':
        adjustment += int(fixup.group(2))
      else:
        adjustment -= int(fixup.group(2))

      current_position = fixup.end()
      next_fixup = fixups.search(content, current_position)

      if adjustment != 0:
        if next_fixup is None:
          content = adjust_headers(content, adjustment, fixup.end())
        else:
          content = adjust_headers(content, adjustment, fixup.end(), next_fixup.start())

      fixup = next_fixup

    return content
  content = process_fixup(content)

  content = re.compile('<!--END %s-->.*?<!--START %s-->' % (select,select), re.DOTALL).sub('', content)
  content = re.compile('<!--END %s-->.*' % select, re.DOTALL).sub('', content)

  content = re.sub('<!--(START|END) [-\w]+-->\n?', '', content)

  # select based on the value of PUB
  if vars['PUB'] == '1':
    content = re.compile('^<!--PUB-N-->.*?\n', re.M).sub('', content)
    content = re.compile('^<!--PUB-Y-->', re.M).sub('', content)
  else:
    content = re.compile('^<!--PUB-Y-->.*?\n', re.M).sub('', content)
    content = re.compile('^<!--PUB-N-->', re.M).sub('', content)

  stdout.write(content)

if __name__ == '__main__':
  if len(sys.argv)>1 and sys.argv[1] == '2dcontext':
    select = '2dcontext'
  elif len(sys.argv)>1 and sys.argv[1] == 'microdata':
    select = 'microdata'
  else:
    select = 'w3c-html'

  main(sys.stdin, sys.stdout, select)
