
''' Pluggable sidebar widget that shows the structure of the source 
file currently being edited '''

import kate
from kate import Kate # Kate library API

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyKDE4.kdeui import KIcon
from PyKDE4.ktexteditor import KTextEditor # KTE namespace


def verticalGradient(top, bottom):
    g = QLinearGradient(0, 0, 0, SourceList.ItemHeight)
    # g.setCoordinateMode(QGradient.StretchToDeviceMode)
    g.setColorAt(0, QColor(top))
    g.setColorAt(1, QColor(bottom))
    return QBrush(g)


class StructureItem(QListWidgetItem):
    ''' Represents something in a source document -- a global variable,
    a function, etc. Each of these has a line (on which their definition
    begins), a name, and a brush to fill the background with, but may
    have more information such as parameters. '''
    def __init__(self, line, name, brush):
        QListWidgetItem.__init__(self)
        self.line = line
        self.setText(name)
        self.setBackground(brush)
        # brush.
        self.name = name.strip()
        self.setSizeHint(QSize(1000, SourceList.ItemHeight))
    
    # helper
    def brushHelper(self, brush, penColor=210):
        if not hasattr(self.__class__, '_brush'):
            # and draw a thin line
            i = QImage(1, SourceList.ItemHeight, QImage.Format_RGB32)
            p = QPainter(i)
            p.fillRect(i.rect(), brush)
            p.setPen(QPen(QColor(penColor, penColor, penColor)))
            p.drawLine(0, SourceList.ItemHeight - 1, 1, SourceList.ItemHeight - 1)
            p.end()
            self.__class__._brush = QBrush(i)
        return self.__class__._brush


class GlobalVariable(StructureItem):
    def __init__(self, line, name):
        gradientBrush = verticalGradient('#ede0b2', '#f3eacd')
        StructureItem.__init__(self, line, name, self.brushHelper(gradientBrush))

class Function(StructureItem):
    ''' A function or procedure. It is up to you what you give as the
    name (i.e. you may choose to include parameters or return types
    in it depending on your language) '''
    brush = None
    def __init__(self, line, name):
        gradientBrush = verticalGradient('#dbedaa', '#e7f3c7')
        StructureItem.__init__(self, line, name, self.brushHelper(gradientBrush))

class Class(StructureItem):
    def __init__(self, line, name):
        gradientBrush = verticalGradient('#c4dbf1', '#c8dff6')
        StructureItem.__init__(self, line, name, self.brushHelper(gradientBrush, penColor=190))

class Method(StructureItem):
    ''' A method is a function member of a class. '''
    def __init__(self, line, name):
        ''' Pass the usual line and name as well as a reference
        to the class that it is a method of '''
        gradientBrush = verticalGradient('#d3ebf9', '#e3f0f7')
        StructureItem.__init__(self, line, '    %s' % name, self.brushHelper(gradientBrush))

class Property(StructureItem):
    ''' Properties are things on a class that always have a method
    for getting a value, most of the time a method for setting this
    value, and sometimes a method for deleting or clearing the value.
    They are used as syntactic sugar in some programming languages or
    as additional meta information. '''
    def __init__(self, line, name, getter, setter=None, deleter=None):
        # we override the widget for this list item
        # because we need ultimo power in our custom display,
        # so do nothing but store data now.
        StructureItem.__init__(self, line)
        self.name = name
        self.getter = getter
        self.setter = setter
        self.deleter = deleter


# class FadeWidget(QWidget):
    # def __init__(self, endColor, parent=None):
        # QWidget.__init__(self, parent)
        # self.endColor = endColor
        # self.gradient = None
        
    # def resizeEvent(self, e):
        # self.gradient = QLinearGradient(QPointF(0, 0), QPointF(self.width(), 0))
        # self.gradient.setColorAt(0, QColor(Qt.transparent))
        # self.gradient.setColorAt(1, QColor(self.endColor))
    
    # def paintEvent(self, e):
        # if self.gradient is not None:
            # QPainter(self).fillRect(self.rect(), QBrush(self.gradient))


class SourceList(QListWidget):
    ItemHeight = 0
    def __init__(self, parent):
        QListWidget.__init__(self, parent)
        self._structure = []
        # disable eliding of the items so that we can add our fade
        self.setTextElideMode(Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # stupid hack for a PyQt4 bug:
        # QGradiant doesn't seem to have setCoordinateMode member.
        self.addItem('Blah')
        SourceList.ItemHeight = self.sizeHintForRow(0) + 2
        self.clear()
        #
        # self.fade = FadeWidget(Qt.white, self)
        # self.fade.resize(20, 100)
        #
        self.setStyleSheet('QListView { show-decoration-selected: 1; } QListView::item:selected { color: white; background: #999 }')
        self.connect(self, SIGNAL('activated(const QModelIndex &)'), self.itemActivated)
    
    def itemActivated(self, index):
        line = self.item(index.row()).line
        self.clearSelection()
        self.emit(SIGNAL('itemOnLineSelected(int)'), line)
    
    # def resizeEvent(self, e):
        # # move the fading-out bit to the right
        # viewport = self.viewport()
        # w = viewport.width()
        # h = viewport.height()
        # fadeWidth = 20
        # self.fade.setFixedSize(QSize(fadeWidth, h))
        # self.fade.move(w - fadeWidth + self.frameWidth(), self.frameWidth())
    
    def setStructure(self, structure):
        ''' Set the source list structure. You do not need to call this or touch
        this class at all if you're merely writing a plugin for a language.
        The format of "structure" is a list of StructureItem subclasses '''
        self.clear()
        self._structure = structure[:]
        for i, item in enumerate(structure):
            self.addItem(item)
    

class SourceStructureWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.sourceList = SourceList(self)
        self.connect(self.sourceList, SIGNAL('itemOnLineSelected(int)'), self.goToLine)
        layout = QVBoxLayout(self)
        layout.setMargin(0)
        layout.addWidget(self.sourceList)
    
    def setStructure(self, structure):
        if structure is None:
            pass
        else:
            self.sourceList.setStructure(structure)
    
    def goToLine(self, line):
        view = kate.activeView()
        cursor = view.cursorPosition()
        lineLength = len(unicode(view.document().line(line)))
        view.setCursorPosition(KTextEditor.Cursor(line, lineLength))
        kate.centralWidget().setFocus(Qt.OtherFocusReason)
        # self.sourceList.clearSelection()
        # self.sourceList.clearFocus()


# the singletoninstance that's used. This is added to the Kate sidebar
# on init
sidebar = SourceStructureWidget()

@kate.init
def attachSourceSidebar():
    ''' Create the side bar (or "tool view" in Kate-speak) and attach it
    to the Kate window '''
    w = kate.mainInterfaceWindow()
    # createToolView parameters:
    # * an arbitrary ID
    # * initial position on the window
    # * icon
    # * label
    icon = KIcon('applications-development').pixmap(16)
    tool = w.createToolView('source_view', Kate.MainWindow.Left, icon, '  Source  ')
    sidebar.setParent(tool)
    # show it too. It sucks that the tool view loads a little after the application,
    # so that your preference on its visibility isn't remembered. Disable the plugin
    # if you don't like it :(
    w.showToolView(tool)
    
    Human = Class(30, 'Human')
    sidebar.setStructure([
        GlobalVariable(3, '__name__'),
        GlobalVariable(4, '__author__'),
        Function(6, 'print(string, end=\'\\n\')'),
        Function(10, 'exit()'),
        Human,
        Method(31, '__init__(self)'),
        Method(35, '__del__(self)'),
        Method(38, 'setName(self, name)'),
        Method(45, 'sayMyName(self)'),
    ])

