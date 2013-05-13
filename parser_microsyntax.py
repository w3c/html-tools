#!/usr/bin/env python

import re, sys

def debug(text):
    # sys.stderr.write("%s\n" % text)
    pass

def list_re(strs):
    return "|".join([re.escape(s) for s in strs])

class IdGenerator:
    def __init__(self, prefix):
        self.prefix = prefix

    def id_from_string(self, string):
        return re.sub('\s', lambda x: '-', self.title_from_string(string))

    def title_from_string(self, string):
        return ("%s %s" % (self.prefix, string)).lower()

class Switch(IdGenerator):
    def __init__(self, switch_var, prefix):
        IdGenerator.__init__(self, prefix)
        self.cases = []
        self.variable = switch_var

    def addCase(self, case):
        self.cases.append(case)

    def text(self):
        return """switch using %s
%s""" % (self.variable, "\n".join([case.text() for case in self.cases]))

    def html(self):
        return """<dl class=switch>%s
</dl>""" % "\n".join([case.html() for case in self.cases])

    def varHtml(self):
        return """<var title="%s">%s</var>""" % (
            self.title_from_string(self.variable), self.variable)

class Case(IdGenerator):
    def __init__(self, case_thingy, switch):
        IdGenerator.__init__(self, "%s %s:" % (switch.prefix, switch.variable))
        self.thingy = case_thingy
        self.conditions = []
        self.switch = switch

    def addCondition(self, condition):
        self.conditions.append(condition)

    def text(self):
        return """  case %s
%s""" % (self.thingy, "\n".join([condition.text() for condition in self.conditions]))

    def html(self):
        return """<dt>If %s is "%s"</dt>
<dd>
<p>Run the appropriate substeps from the following list:</p>
<dl class=switch>%s
</dl>
</dd>""" % (self.switch.varHtml(), self.thingyHtml(),
            "\n".join([condition.html() for condition in self.conditions]))

    def thingyHtml(self):
        return """<dfn id=%s title="%s">%s</dfn>""" % (
            self.id_from_string(self.thingy),
            self.title_from_string(self.thingy),
            self.thingy)

common_microsyntaxes = ["space character", "0-9", "letter"]

# Yes, this should be generic code. No, I can't be bothered right now.
single_characters = {
    ".": "a U+002E FULL STOP character (.)",
    "-": "a U+002D HYPHEN-MINUS character (-)",
    "e/E": "a U+0045 LATIN CAPITAL LETTER E character or a U+0065 LATIN SMALL LETTER E character"
}

class Condition:
    def __init__(self, variable=None, characters=None, ifunless=None, subcondition=None):
        self.variable = variable
        self.characters = characters
        self.ifunless = ifunless
        self.subcondition = subcondition
        self.statements = []

    def addStatement(self, statement):
        self.statements.append(statement)

    def text(self):
        return """    %s=%s</dt>
<dd>
%s
</dd>""" % (self.variable, self.conditionalText, "\n".join([statement.text() for statement in self.statements]))

    def html(self):
        return """<dt>If %s is %s</dt>
<dd>
%s
</dd>""" % (self.varHtml(), self.conditionalHtml(), "\n".join([statement.html() for statement in self.statements]))

    def varHtml(self, var=None):
        if var is None:
            var = self.variable
        return """<var title="">%s</var>""" % var

    def conditionalHtml(self):
        conditional = ""
        if self.characters in common_microsyntaxes:
            conditional = self.microsyntaxHtml()
        elif self.characters == "eof":
            return "EOF"
        else:
            conditional = single_characters[self.characters]
        if self.ifunless is not None:
            conditional += " and %s is %s" % (
                self.varHtml(self.subcondition),
                "true" if self.ifunless == "if" else "false")
        return conditional

    def microsyntaxHtml(self):
        if self.characters == "space character":
            return "a <a href=#space-character>space character</a>"
        elif self.characters == "0-9":
            return """an <a href=#ascii-digits title="ASCII digits">ASCII digit</a>"""
        elif self.characters == "letter":
            return """an <a href=#uppercase-ascii-letters title="uppercase ASCII letters">uppercase ASCII letter</a> or a <a href=#lowercase-ascii-letters title="lowercase ASCII letters">lowercase ASCII letter</a>"""
        else:
            raise Exception, "This should never happen."

class Otherwise(Condition):
    def __init__(self):
        Condition.__init__(self)

    def text(self):
        return """    otherwise:
%s""" % "\n".join([statement.text() for statement in self.statements])

    def html(self):
        return """<dt>Otherwise</dt>
<dd>
%s
</dd>""" % "\n".join([statement.html() for statement in self.statements])

class Statement:
    def __init__(self):
        pass

constants = ["true", "false"]

class Assignment(Statement,IdGenerator):
    def __init__(self, lval, rval, variables_re,case):
        Statement.__init__(self)
        self.lval = lval
        self.rval = rval
        self.variables_re = variables_re
        self.prefix = case.prefix

    def text(self):
        return "      %s := %s" % (self.lval, self.rval)

    def html(self):
        return """<p>Set %s to %s.</p>""" % (self.lvalHtml(), self.rvalHtml())

    def lvalHtml(self):
        return """<var title="">%s</var>""" % self.lval

    def rvalHtml(self):
        if self.rval in constants:
            return self.rval
        elif self.variables_re.match(self.rval):
            return """the value of <var title="%s">%s</var>""" % (
                self.title_from_string(self.rval), self.rval)
        else:
            return "\"<a href=#%s title=\"%s\">%s</a>\"" % (
                self.id_from_string(self.rval),
                self.title_from_string(self.rval),
                self.rval)

class Buffer(Statement):
    def __init__(self, var):
        Statement.__init__(self)
        self.variable = var

    def text(self):
        return "      buffer %s" % self.variable

    def html(self):
        return """<p>Append %s to <var title="">buffer</var>.</p>
""" % self.varHtml()

    def varHtml(self):
        return """<var title="">%s</var>""" % self.variable

class Decrement(Statement):
    def __init__(self, var):
        Statement.__init__(self)
        self.variable = var

    def text(self):
        return "      dec %s" % self.variable

    def html(self):
        return """<p>Decrement %s by one.</p>""" % self.varHtml()

    def varHtml(self):
        return """<var title="">%s</var>""" % self.variable

class Nop(Statement):
    def __init__(self):
        Statement.__init__(self)

    def text(self):
        return "      nop"

    def html(self):
        return "<p>Do nothing.</p>"

class Post(Statement):
    def __init__(self, var, post_target):
        Statement.__init__(self)
        self.variable = var
        self.target = post_target

    def text(self):
        return "      post %s" % self.variable

    def html(self):
        return """<p>Append %s to %s.</p>""" % (self.varHtml(), self.target)

    def varHtml(self):
        return """<var title="">%s</var>""" % self.variable

class Predefined(Statement,IdGenerator):
    def __init__(self, statement, prefix):
        Statement.__init__(self)
        self.statement = statement
        self.prefix = prefix

    def text(self):
        return "      %s" % self.statement

    def html(self):
        return """<p><a href=#%s title="%s">%s</a>.</p>""" % (self.id_from_string(self.statement),
       self.title_from_string(self.statement),
       self.statement.capitalize())

IN_PREAMBLE=0
IN_SWITCH=1
IN_CASE=2
IN_CONDITION=3
parse_var_decls = re.compile('^\s*<pre>parse using (.*)$')
parse_targets = re.compile('^\s*(posting|buffering) to: (.*)$')
parse_defined_above = re.compile('^\s*defined above: (.*)$')
parse_xref_prefix = re.compile('^\s*prefix xrefs with ["](.+)["]$')
parse_switch = re.compile('^\s*switch using (.+)$')
parse_case = re.compile('^\s*case (.+):$')
parse_otherwise = re.compile('^\s*otherwise:$')
parse_assignment = re.compile('^\s*(.+) := (.+)$')
parse_buffer = re.compile('^\s*buffer (.+)$')
parse_decrement = re.compile('^\s*dec (.+)$')
parse_nop = re.compile('^\s*nop$')
parse_post = re.compile('^\s*post (.+)$')

class StateMachine:
    def __init__(self):
        self.state = IN_PREAMBLE
        self.variables = None
        self.posting_to = None
        self.buffering_to = None
        self.condition_re = None
        self.predefined_re = None
        self.switch = None
        self.variables_re = None
        self.xref_prefix = None

    def check_case(self, line):
        case = parse_case.match(line)
        if case is not None:
            self.case = Case(case.group(1), self.switch)
            self.switch.addCase(self.case)
            self.state = IN_CASE

    def check_condition(self, line):
        condition = self.condition_re.match(line)
        if condition is not None:
            self.condition = Condition(
                condition.group(1), condition.group(3),
                condition.group(6), condition.group(8))
            self.case.addCondition(self.condition)
            self.state = IN_CONDITION

    def check_otherwise(self, line):
        otherwise = parse_otherwise.match(line)
        if otherwise is not None:
            self.condition = Otherwise()
            self.case.addCondition(self.condition)
            self.state = IN_CONDITION

    def process_line(self, line):
        debug("process_line(%s) in state %s" % (line, self.state))
        if self.state == IN_PREAMBLE:
            var_decls = parse_var_decls.match(line)
            if var_decls is not None:
                self.variables = var_decls.group(1).split(", ")
                self.variables_re_str = "(%s)" % list_re(self.variables)
                self.variables_re = re.compile(self.variables_re_str)
                return
            targets = parse_targets.match(line)
            if targets is not None:
                if (targets.group(1) == "posting"):
                    self.posting_to = targets.group(2)
                elif (targets.group(1) == "buffering"):
                    self.buffering_to = targets.group(2)
                return
            predefs = parse_defined_above.match(line)
            if predefs is not None:
                self.predefineds = predefs.group(1).split(", ")
                self.predefined_re = re.compile("^\s*(%s)$" % list_re(self.predefineds))
                return
            xrefs = parse_xref_prefix.match(line)
            if xrefs is not None:
                self.xref_prefix = xrefs.group(1)
                return
            switch = parse_switch.match(line)
            if switch is not None:
                self.condition_re = re.compile("^\s*(%s)=(%s|eof|[-.A-Za-z](/[A-Za-z])*)( (if|unless)( (%s|numbers are( not)? coming)))?:$" % (
                    self.variables_re_str,
                    list_re(common_microsyntaxes),
                    self.variables_re_str))
                self.switch = Switch(switch.group(1), self.xref_prefix)
                self.state = IN_SWITCH
                return
        elif self.state == IN_SWITCH:
            self.check_case(line)
        elif self.state == IN_CASE:
            self.check_condition(line)
        elif self.state == IN_CONDITION:
            self.check_condition(line)
            self.check_otherwise(line)
            self.check_case(line)
            assignment = parse_assignment.match(line)
            if assignment is not None:
                self.condition.addStatement(Assignment(
                    assignment.group(1), assignment.group(2),
                    self.variables_re, self.case))
                return
            buffer = parse_buffer.match(line)
            if buffer is not None:
                self.condition.addStatement(Buffer(buffer.group(1)))
                return
            post = parse_post.match(line)
            if post is not None:
                self.condition.addStatement(Post(post.group(1),
                                                 self.posting_to))
                return
            predefined = self.predefined_re.match(line)
            if predefined is not None:
                self.condition.addStatement(Predefined(predefined.group(1),
                                                       self.switch.prefix))
                return
            decrement = parse_decrement.match(line)
            if decrement is not None:
                self.condition.addStatement(Decrement(decrement.group(1)))
                return
            nop = parse_nop.match(line)
            if nop is not None:
                self.condition.addStatement(Nop())
                return

    def text(self):
        return """parse using %s
posting to: %s
buffering to: %s
defined above: %s
prefix xrefs with "%s"
%s""" % (self.variables, self.posting_to, self.buffering_to,
        self.predefined_re, self.switch.prefix, self.switch.text())

    def html(self):
        return self.switch.html()

def process_doc(doc):
    in_pseudocode = False
    parser = None
    start = re.compile('^\s*<pre>parse using')
    end = re.compile('^\s*</pre>')
    for line in doc:
        if in_pseudocode:
            if end.match(line) is not None:
                in_pseudocode = False
                yield parser.html()
            else:
                parser.process_line(line)
        elif start.match(line) is not None:
            in_pseudocode = True
            parser = StateMachine()
            parser.process_line(line)
        else:
            yield line

def main(infile, outfile):
    for line in process_doc(infile):
        outfile.write(line)

if __name__ == '__main__':
    main(sys.stdin, sys.stdout)
