#!/usr/bin/python
# Python port of http://people.w3.org/mike/fixes/bs.pl
# This brief script (33 lines) implements the change proposal for
# HTML WG issue 150 aka "code-point-verbosity", resulting in a
# 3738-line patch for the HTML5 spec.
# http://lists.w3.org/Archives/Public/public-html/2011Feb/0120.html
# https://www.w3.org/Bugs/Public/show_bug.cgi?id=11124
def main(stdin, stdout):
  import re,sys
  original_para = re.compile('<p>The\s+<dfn\s+id="alphanumeric-ascii-characters">alphanumeric\s+ASCII\s+characters<\/dfn>\s+are\s+those\s+in\s+the\s+ranges\s+U\+0030\s+DIGIT\s+ZERO\s+\(0\)\s+to\s+U\+0039\s+DIGIT\s+NINE\s+\(9\),\s+U\+0041\s+LATIN\s+CAPITAL\s+LETTER\s+A\s+to\s+U\+005A\s+LATIN\s+CAPITAL\s+LETTER\s+Z,\s+U\+0061\s+LATIN\s+SMALL\s+LETTER\s+A\s+to\s+U\+007A\s+LATIN\s+SMALL\s+LETTER\s+Z.<\/p>')
  uppercase = '<p>The <dfn id="uppercase-ascii-letters">uppercase ASCII letters</dfn> are those in the range U+0041 LATIN CAPITAL LETTER A to U+005A LATIN CAPITAL LETTER Z.</p>'
  lowercase = '  <p>The <dfn id="lowercase-ascii-letters">lowercase ASCII letters</dfn> are those in the range U+0061 LATIN SMALL LETTER A to U+007A LATIN SMALL LETTER Z.</p>'
  digits = '  <p>The <dfn id="ascii-digits">ASCII digits</dfn> are those in the range U+0030 DIGIT ZERO (0) to U+0039 DIGIT NINE (9).</p>'
  dummy_replacement = '@DUMMYREPLACEMENT@'
  replacement_para = uppercase + "\n\n" + lowercase + "\n\n" + digits
  cap_a_z = re.compile('U\+0041\s+LATIN\s+CAPITAL\s+LETTER\s+A\s+to\s+U\+005A\s+LATIN\s+CAPITAL\s+LETTER\s+Z')
  small_a_z = re.compile('U\+0061\s+LATIN\s+SMALL\s+LETTER\s+A\s+to\s+U\+007A\s+LATIN\s+SMALL\s+LETTER\s+Z')
  zero_nine = re.compile('U\+0030\s+DIGIT\s+ZERO\s+\(0\)\s+to\s+U\+0039\s+DIGIT\s+NINE\s+\(9\)')
  uppercase_ref = '<a href="#uppercase-ascii-letters">uppercase ASCII letters</a>'
  lowercase_ref = '<a href="#lowercase-ascii-letters">lowercase ASCII letters</a>'
  digits_ref = '<a href="#ascii-digits">ASCII digits</a>'
  unicode_char =  re.compile('(U\+[A-F0-9]{4})\s[A-Z\s-]+(\scharacter(s)?)?\s\((.{1,4})\)')
  def unicode_replacement(matchobj):
    groups = list(matchobj.groups())
    if not groups[1]: groups[1] = ''
    return '"%s" (%s)%s' % (groups[3], groups[0], groups[1])
  source=stdin.read()
  source = original_para.sub(dummy_replacement, source)
  source = cap_a_z.sub(uppercase_ref, source)
  source = small_a_z.sub(lowercase_ref, source)
  source = zero_nine.sub(digits_ref, source)
  source = source.replace(dummy_replacement,replacement_para)
  source = unicode_char.sub(unicode_replacement, source)
  stdout.write(source)

if __name__ == '__main__':
  main(sys.stdin, sys.stdout)
