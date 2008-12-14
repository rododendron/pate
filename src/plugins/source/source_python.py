
''' Source plugin analyser for Python code '''

from cStringIO import StringIO
import compiler # builtin python -> AST compiler
import compiler.ast
import time

import source


@source.register('text/x-python')
def analyse(s):
    start = time.time()
    try:
        ast = compiler.parse(s)
    except SyntaxError:
        return
    topLevel = ast.node
    structure = []
    for node in topLevel.nodes:
        if isinstance(node, compiler.ast.Assign):
            assignmentName, assignmentValue = node.getChildren()
            if not isinstance(assignmentName, compiler.ast.AssName):
                continue
            line = assignmentName.lineno - 1
            structure.append(source.GlobalVariable(line, assignmentName.name))
        elif isinstance(node, compiler.ast.Function):
            name = node.name
            # name = '%s(%s)' % (node.name, ', '.join(node.argnames))
            structure.append(source.Function(node.lineno - 1, name))
        elif isinstance(node, compiler.ast.Class):
            # XX list superclasses (node.bases)?
            name = node.name
            structure.append(source.Class(node.lineno - 1, name))
            classBlock = node.code
            nameToMethod = {}
            for classItem in classBlock.nodes:
                if isinstance(classItem, compiler.ast.Function):
                    name = classItem.name
                    # name = '%s(%s)' % (classItem.name, ', '.join(classItem.argnames))
                    method = source.Method(classItem.lineno - 1, name)
                    nameToMethod[classItem.name] = method
                    structure.append(method)
                if isinstance(classItem, compiler.ast.Assign):
                    # does this seem to be a property?
                    assignmentName, assignmentValue = classItem.getChildren()
                    if isinstance(assignmentValue, compiler.ast.CallFunc) and assignmentValue.asList()[0].name == 'property':
                        getter = setter = deleter = None
                        methods = [nameToMethod.get(x.name) for x in assignmentValue.args]
                        structure.append(source.Property(assignmentName.lineno - 1, assignmentName.name, *methods))
    return structure


# import pprint
# pprint.pprint(analyse('''

# class A(B, C, D):         
    # def __init__(self, x=True):
        # pass                   
    # def foo(self):             
        # return                 
    # foo = property(getFoo, setFoo)




# '''))
