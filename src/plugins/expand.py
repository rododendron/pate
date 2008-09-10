
import kate


class ParseError(Exception):
    pass

wordBoundary = set(u' \t"\';[]{}()#:/\\,+=!?%^|&*~`')

def wordAtCursor(document, view=None):
    view = view or document.activeView()
    cursor = view.cursorPosition()
    line = unicode(document.line(cursor.line()))
    start, end = wordAtCursorPosition(line, cursor)
    return line[start:end]

def wordAtCursorPosition(line, cursor):
    ''' Get the word under the active view's cursor in the given 
    document '''
    # better to use word boundaries than to hardcode valid letters because
    # expansions should be able to be in any unicode character.
    start = end = cursor.column()
    if start == len(line) or line[start] in wordBoundary:
        start -= 1
    while start >= 0 and line[start] not in wordBoundary:
        start -= 1
    start += 1
    while end < len(line) and line[end] not in wordBoundary:
        end += 1
    return start, end

def wordAndArgumentAtCursor(document, view=None):
    view = view or document.activeView()
    word_range, argument_range = wordAndArgumentAtCursorRanges(document, view.cursorPosition())
    if word_range.isEmpty():
        word = None
    else:
        word = unicode(document.text(word_range))
    if not argument_range or argument_range.isEmpty():
        argument = None
    else:
        argument = unicode(document.text(argument_range))
    return word, argument

def wordAndArgumentAtCursorRanges(document, cursor):
    line = unicode(document.line(cursor.line()))
    column_position = cursor.column()
    # special case: cursor past end of argument
    argument_range = None
    if cursor.column() > 0 and line[cursor.column() - 1] == ')':
        argument_end = kate.KTextEditor.Cursor(cursor.line(), cursor.column() - 1)
        argument_start = matchingParenthesisPosition(document, argument_end, opening=')')
        argument_end.setColumn(argument_end.column() + 1)
        argument_range = kate.KTextEditor.Range(argument_start, argument_end)
        cursor = argument_start
    line = unicode(document.line(cursor.line()))
    start, end = wordAtCursorPosition(line, cursor)
    word_range = kate.KTextEditor.Range(cursor.line(), start, cursor.line(), end)
    word = line[start:end]
    if argument_range is None and word:
        if end < len(line) and line[end] == '(':
            # ruddy lack of attribute type access from the KTextEditor
            # interfaces.
            argument_start = kate.KTextEditor.Cursor(cursor.line(), end)
            argument_end = matchingParenthesisPosition(document, argument_start, opening='(')
            argument_range = kate.KTextEditor.Range(argument_start, argument_end)
    return word_range, argument_range


def matchingParenthesisPosition(document, position, opening='('):
    closing = ')' if opening == '(' else '('
    delta = 1 if opening == '(' else -1
    # take a copy, Cursors are mutable
    position = position.__class__(position)
    
    level = 0
    state = None
    while 1:
        character = unichr(document.character(position).unicode())
        print 'character:', repr(character)
        if state in ('"', "'"):
            if character == state:
                state = None
        else:
            if character == opening:
                level += 1
            elif character == closing:
                level -= 1
                if level == 0:
                    if closing == ')':
                        position.setColumn(position.column() + delta)
                    break
            elif character in ('"', "'"):
                state = character
        
        position.setColumn(position.column() + delta)
        # must we move down a line?
        if document.character(position).isNull():
            position.setPosition(position.line() + delta, 0)
            # failure again => EOF
            if document.character(position).isNull():
                raise ParseError('end of file reached')
            else:
                if state in ('"', "'"):
                    raise ParseError('end of line while searching for %s' % state)
    return position



@kate.action('Expand', shortcut='Ctrl+E', menu='Edit')
def expandAtCursor():
    document = kate.activeDocument()
    try:
        word_range, argument_range = wordAndArgumentAtCursorRanges(document)
    except ParseError, e:
        print 'Parse error:', e
        return
    # get word and try to find word in map
    document.startEditing()
    if argument_range is not None:
        argument = unicode(document.text(argument_range))
        document.removeText(argument_range)
    else:
        argument = None
    document.endEditing()
# while ( cursor.column() > 0 && highlight()->isInWord( l->at( cursor.column() - 1 ), l->attribute( cursor.column() - 1 ) ) )
          # cursor.setColumn(cursor.column() - 1);
        # old = text( KTextEditor::Range(cursor, 1) );
