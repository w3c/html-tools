import re, math
entity = re.compile('<code.*?>(.*?)</code>.*?<td> (.*?) </td>')
hex_strings = re.compile('[0-9a-fA-F]+')

def entity_processor_json(input, json):
  json.write('{\n')
  last = None
  for line in input:
    match = entity.search(line)
    name, points =  match.groups(1)
    points = hex_strings.findall(points)
    if len(points) == 1:
      codepoint = int(points[0], 16)
      if codepoint <= 0xFFFF:
        data = '"codepoints": [%d], "characters": "\u%0.4X"' %  \
          (codepoint, codepoint)
      else:
        highSurrogate = int(math.floor((codepoint - 0x10000) / 0x400) + 0xD800)
        lowSurrogate = int((codepoint - 0x10000) % 0x400 + 0xDC00)
        data = '"codepoints": [%d], "characters": "\u%0.4X\u%0.4X"' %\
          (codepoint, highSurrogate, lowSurrogate)
    else:
      points = map(lambda s: int(s, 16), points)
      data = '"codepoints": [%d, %d], "characters": "\u%0.4X\u%0.4X"' %\
        (points[0], points[1], points[0], points[1])
    if last: json.write(last + ',\n')
    last = '  "&%s": { %s }' % (name, data)
  json.write(last + "\n")
  json.write('}\n')

if __name__ == '__main__':
  import sys
  entity_processor_json(sys.stdin, sys.stdout) 
