
''' Source plugin analyser for C/C++ code. 
Unlike the Python counterpart, this does not use a real parser.
Any patch to fix that would be greatly appreciated ;).

XX this hasn't really been implemented yet. Some TLC would be
very appreciated '''


import re

# import source


stringExpression = r'"(?:[^"]|\\")*"(?!")'
singleLineCommentExpression = '//.*'
multiLineCommentExpression = r'/\*(?:.|\n)*\*/'
if0Expression = r'^#[\t ]*if 0(?:.|\n)*\n#[\t ]*endif'


def emptyStrings(source):
    def empty(match):
        ''' Empty a string. Removes everything except newlines '''
        if match.group('string'):
            return '"%s"' % ''.join(x for x in match.group()[1:-1] if x == '\n')
        elif match.group('multi'):
            # print 'multi:', match.group()
            return '/*%s*/' % ''.join(x for x in match.group()[2:-2] if x == '\n')
        elif match.group('single'):
            return '//'
        elif match.group('ifzero'):
            return '#if 0%s#endif' % ''.join(x for x in match.group() if x == '\n')
        else:
            return match.group()
    return re.compile(r'(?:(?P<string>%s)|(?P<single>%s)|(?P<multi>%s)|(?m)(?!x)(?P<ifzero>%s))' % (stringExpression, singleLineCommentExpression, multiLineCommentExpression, if0Expression)).sub(empty, source)

def emptyPreprocessorLines(source):
    ''' Empty all preprocessor lines except #defines '''
    # print source
    def empty(match):
        bits = match.group().split()
        if len(bits) == 1:
            return '#'
        # "# define foo" => "#define foo"
        if bits[0] == '#':
            bits[0:2] = [bits[0] + bits[1]]
        if bits[0] == '#define' and len(bits) > 2:
            bits = ' '.join(bits).split(None, 2)
            bits[2] = ''.join(x for x in bits[2] if x == '\1')
            print bits
            return ' '.join(bits)
        return '#'
    source = source.replace('\\\n', '\1')
    source = re.compile('^#.*', re.MULTILINE).sub(empty, source)
    return source.replace('\1', '\\\n')


identifier = '[A-Za-z_]\w*'
classExpression = re.compile('\s*class\s+(%s)' % identifier)
functionExpression = re.compile('\b(%s)\s+(%s)\s*\((.*)\)' % (identifier, identifier))

def analyse(s):
    # plan of attack:
    # 1. Strip out the contents of strings, comments, and if 0 blocks
    # 2. Ignore preprocessors except defines.
    # 3. Assume 
    s = emptyStrings(s)
    print s
    print
    print '-------------'
    print 
    structure = []
    for match in classExpression.finditer(s):
        try:
            classStart = s.index('{', match.start()) + 1
        except IndexError:
            continue
        className = match.group(0)
        braces = 1
        cursor = classStart
        while braces:
            try:
                character = s[cursor]
            except IndexError:
                break
            if character == '{':
                braces += 1
            elif character == '}':
                braces -= 1
            cursor += 1
        if braces:
            print braces
            continue
        classChunk = s[classStart - 1:cursor]
        # print repr(classChunk)
        # if '~%s' % className
    # print s



def main():
    analyse('''\
#include <iostream>
#define foo
#define bar(x) int bar = 1;\\
               int baz = 2;\\
               int bat = 3;
#if 0
"foooo" this is bad
#endif

class A {
    A();
    int sayName();
};

int main(int argc, char *argv[]) {
    /* test 
    */
    // testing
    std::cout << "Hello world!\\n 
    ";
    // print "hello"
    return 0;
}


''')
    

if __name__ == '__main__':
    main()

