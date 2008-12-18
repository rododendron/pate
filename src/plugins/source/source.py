
''' Pluggable sidebar widget that shows the structure of the source 
file currently being edited '''

import functools
import random
import time
import threading
import sys

import kate
from kate import Kate # Kate library API

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyKDE4.kdeui import KIcon, KLineEdit
from PyKDE4.ktexteditor import KTextEditor # KTE namespace

# time between updates in milliseconds. Note that this doesn't just
# mean that it polls every n milliseconds, but that when you're
# typing it'll wait at least this amount before each call to update
updateInterval = 1000




mimeTypeToAnalyser = {}
def register(*mimeTypes):
    ''' Register a source analyser for a the given
    mimetype(s). Periodically the function will be called in a
    separate thread and fed a string containing the contents of a file
    of registered mime. The function must return a list of 
    StructureItem subclasses as appropriate to describe the file's
    structure. See source_python.py for an example.
    
    Behaviour is undefined if more than one plugin registers
    for the same mimetype '''
    def inner(func):
        for mimeType in mimeTypes:
            mimeTypeToAnalyser[mimeType] = func
        return func
    return inner


@kate._attribute(cache={})
def gradientImageWithLine(fromColor, toColor, penColor=210):
    if (fromColor, toColor, penColor) not in gradientImageWithLine.cache:
        brush = verticalGradient(fromColor, toColor)
        # and draw a thin line
        i = QImage(1, SourceList.ItemHeight, QImage.Format_RGB32)
        p = QPainter(i)
        p.fillRect(i.rect(), brush)
        p.setPen(QPen(QColor(penColor, penColor, penColor)))
        p.drawLine(0, SourceList.ItemHeight - 1, 1, SourceList.ItemHeight - 1)
        p.end()
        gradientImageWithLine.cache[fromColor, toColor, penColor] = i
    return gradientImageWithLine.cache[fromColor, toColor, penColor]


class StructureItem(QListWidgetItem):
    ''' Represents something in a source document -- a global variable,
    a function, etc. Each of these has a line (on which their definition
    begins), a name, and a brush to fill the background with, but may
    have more information such as parameters. '''
    def __init__(self, line, name, backgroundImage):
        QListWidgetItem.__init__(self)
        self.line = line
        self.setText(name)
        self.backgroundImage = backgroundImage
        # brush.
        self.name = name.strip()
        self._longName = None
        self.setSizeHint(QSize(1000, SourceList.ItemHeight))
    
    def _get_longName(self):
        if self._longName is not None:
            return self._longName
        else:
            return self.name
    def _set_longName(self, longName):
        self._longName = longName
    longName = property(_get_longName, _set_longName)
    
    def beforeAddedToListWidget(self):
        # called before this is put on a listwidget
        if not hasattr(self.__class__, 'BackgroundBrush'):
            self.__class__.BackgroundBrush = QBrush(self.backgroundImage)
        self.setBackground(self.__class__.BackgroundBrush)


class GlobalVariable(StructureItem):
    def __init__(self, line, name):
        StructureItem.__init__(self, line, name, gradientImageWithLine('#ede0b2', '#f3eacd'))

class Function(StructureItem):
    ''' A function or procedure. It is up to you what you give as the
    name (i.e. you may choose to include parameters or return types
    in it depending on your language) '''
    brush = None
    def __init__(self, line, name):
        StructureItem.__init__(self, line, name, gradientImageWithLine('#dbedaa', '#e7f3c7'))

class Class(StructureItem):
    def __init__(self, line, name):
        StructureItem.__init__(self, line, name, gradientImageWithLine('#c4dbf1', '#c8dff6', 190))

class Method(StructureItem):
    ''' A method is a function member of a class. '''
    def __init__(self, line, name):
        ''' Pass the usual line and name as well as a reference
        to the class that it is a method of '''
        StructureItem.__init__(self, line, '    %s' % name, gradientImageWithLine('#d3ebf9', '#e3f0f7'))

class Property(StructureItem):
    ''' Properties are things on a class that always have a method
    for getting a value, most of the time a method for setting this
    value, and sometimes a method for deleting or clearing the value.
    They are used as syntactic sugar in some programming languages or
    as additional meta information. '''
    def __init__(self, line, name, getter=None, setter=None, deleter=None):
        # we override the widget for this list item
        # because we need ultimo power in our custom display,
        # so do nothing but store data now.
        StructureItem.__init__(self, line, '    %s' % name, gradientImageWithLine('#d3ebf9', '#e3f0f7'))
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
        self._unsupportedMimeType = None
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
    
    # def resizeEvent(self, e):
        # # move the fading-out bit to the right
        # viewport = self.viewport()
        # w = viewport.width()
        # h = viewport.height()
        # fadeWidth = 20
        # self.fade.setFixedSize(QSize(fadeWidth, h))
        # self.fade.move(w - fadeWidth + self.frameWidth(), self.frameWidth())
    
    def itemActivated(self, index):
        line = self.item(index.row()).line
        self.clearSelection()
        self.emit(SIGNAL('itemOnLineSelected(int)'), line)
    
    def setStructure(self, structure):
        ''' Set the source list structure. You do not need to call this or touch
        this class at all if you're merely writing a plugin for a language.
        The format of "structure" is a list of StructureItem subclasses '''
        self._unsupportedMimeType = None
        self._structure = structure[:]
        self.clear()
        for i, item in enumerate(structure):
            item.beforeAddedToListWidget()
            self.addItem(item)
    
    def setUnsupportedMimeType(self, mimeType):
        self._unsupportedMimeType = mimeType
        # v = self.viewport()
        self.clear()
        self.update()
    
    def paintEvent(self, e):
        QListWidget.paintEvent(self, e)
        if self._unsupportedMimeType is not None:
            rect = self.rect()
            p = QPainter(self.viewport())
            # f = p.font()
            document = QTextDocument()
            f = document.defaultFont()
            f.setPixelSize(rect.width() / 12)
            document.setDefaultFont(f)
            textColor = self.palette().mid().color().dark(140).name()
            document.setHtml('<font color="%s"><center>No analyser for<br/><font size="+2"><b>%s</b></font></center></font>' % (textColor, self._unsupportedMimeType))
            rect.adjust(10, 10, -10, -10)
            document.setTextWidth(rect.width() - 20)
            textSize = document.size().toSize()
            p.translate(rect.width() / 2 - textSize.width() / 2, rect.height() / 2 - textSize.height() / 2)
            # textSize.translate
            document.drawContents(p)
            # actualRect = p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, 'No analyser for mimetype\n%s' % self._unsupportedMimeType)


class AnalyseEvent(QEvent):
    Type = QEvent.User + 111
    def __init__(self, mimeType, source):
        QEvent.__init__(self, QEvent.Type(self.Type))
        self.mimeType = mimeType
        self.source = source


class AnalyserThread(QThread):
    ''' Asynchronously analyses a bit of source code and produce
    a structure from it. To start analysing a bit of source,
    pass its mime type and the code to the 'analyse' function.
    When it has finished analysing, the thread will emit an
    'analysed' signal, passing the structure (as a list of 
    StructureItem subclasses).
    To see whether source analysis is underway, check the value
    of the analysing attribute '''
    def __init__(self):
        QThread.__init__(self)
        self.analysing = False
    
    def analyse(self, mimeType, source):
        ''' Start analysing the source to produce the structure.
        When it has been parsed, an 'analysed' signal is emitted.
        You must have called start() on this thread before calling
        this.
        n.b. this function is fully thread-safe '''
        while not hasattr(self, 'o'):
            time.sleep(0.1)
        self.analysing = True
        event = AnalyseEvent(mimeType, source)
        QCoreApplication.postEvent(self.o, event)
    
    def run(self):
        self.o = QObject()
        self.o.customEvent = self.customEventInThread
        self.exec_()
        # self.structure = mimeTypeToAnalyser[self.mimeType](self.source)
        # self.finished = True
    
    def customEventInThread(self, e):
        if e.type() != AnalyseEvent.Type:
            return
        structure = mimeTypeToAnalyser[e.mimeType](e.source)
        self.analysing = False
        self.emit(SIGNAL('analysed'), structure)


class SourceStructureWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.sourceList = SourceList(self)
        self.connect(self.sourceList, SIGNAL('itemOnLineSelected(int)'), self.goToLine)
        layout = QVBoxLayout(self)
        layout.setMargin(0)
        layout.addWidget(self.sourceList)
        self.analyser = AnalyserThread()
        self.connect(self.analyser, SIGNAL('analysed'), self.structureUpdated, Qt.QueuedConnection)
        self.analyser.start()
        self.analysisTimer = QTimer()
        self.connect(self.analysisTimer, SIGNAL('timeout()'), self.analyse)
        self.analysisTimer.setInterval(updateInterval)
        self.analysisTimer.setSingleShot(True)
        self.documentsBeingAnalysed = set()
        self.lastView = None
        # can't rely on lastView.document() if the view gets closed, so
        # we must remember the last document tooo
        self.lastDocument = None
        self.dirty = True
        # kickstart
        QTimer.singleShot(0, self.viewChanged)
    
    def viewChanged(self):
        if self.lastDocument is not None:
            self.disconnect(self.lastDocument, SIGNAL('textChanged(KTextEditor::Document*)'), self.textChanged)
        self.lastView = kate.activeView()
        if self.lastView is None:
            return
        self.lastDocument = self.lastView.document()
        # we can't just not listen for text changes to documents whose mimetype
        # we don't like now, because the mime may change. 
        # XX There's no concise signal for 'mime changed', but maybe something
        # else can be done.
        self.connect(self.lastDocument, SIGNAL('textChanged(KTextEditor::Document*)'), self.textChanged, Qt.QueuedConnection)
        self.dirty = True
        self.textChanged(None, immediate=True)
    
    def textChanged(self, document, immediate=False):
        # don't analyse for a document whose mimetype we know nothing about..
        mimeType = str(kate.activeDocument().mimeType())
        if mimeType not in mimeTypeToAnalyser:
            self.sourceList.setUnsupportedMimeType(mimeType)
            global structure
            structure = None
            # disable symbol jump
            showSymbolFilter.action.setEnabled(False)
            return
        showSymbolFilter.action.setEnabled(True)
        self.dirty = True
        if immediate:
            self.analysisTimer.stop()
            self.analyse()
        elif self.analysisTimer.isActive():
            return
        elif self.analyser.analysing:
            self.analyse()
        else:
            self.analysisTimer.start()
        # self.analysisTimer
        # print 'view change'
    
    def analyse(self):
        document = self.lastView.document()
        self.documentsBeingAnalysed.add(document)
        mimeType = str(document.mimeType())
        source = unicode(document.text())
        self.dirty = False
        self.analyser.analyse(mimeType, source)
    
    def structureUpdated(self, _structure):
        # it's useful for other plugins to have access to this structure.
        global structure
        structure = _structure
        # print QThread.currentThreadId(), 'structure updated'
        # make sure there hasn't been a switch of document in between
        self.documentsBeingAnalysed.remove(kate.activeDocument())
        if self.documentsBeingAnalysed:
            return
        
        if _structure is None:
            pass
        else:
            self.sourceList.setStructure(_structure)
        
    
    # def timerEvent(self, e=None):
        # # print 'timer'
        # if e is not None and e.timerId() != self.analyseTimer:
            # return
        # if self.analyser.analysing:
            # return
        # document = kate.activeDocument()
        # mimeType = str(document.mimeType())
        # source = unicode(document.text())
        # self.analyser.analyse(mimeType, source)
        
        # # if there are any running threads, forget it
        # if self.analysisThread is not None:
            # if self.analysisThread.finished:
                # print 'set structure'
                # self.setStructure(self.analysisThread.structure)
            # else:
                # print 'not finished'
                # return
        # document = kate.activeDocument()
        # mimeType = str(document.mimeType())
        # source = unicode(document.text())
        # if mimeType in mimeTypeToAnalyser:
            # self.analysisThread = AnalyserThread(mimeType, source)
            # print 'started analyser'
            # self.analysisThread.start()
        # else:
            # print 'set structure empty'
            # self.setStructure([])
    
    def goToLine(self, line):
        goToLine(kate.activeView(), line)


class WidgetScreen(QWidget):
    ''' Screen the top level window '''
    def __init__(self, parent, color=QColor(255, 255, 255, 150), child=None):
        QWidget.__init__(self, parent)
        setBackgroundColor(self, color)
        self.child = child
        layout = QVBoxLayout(self)
        layout.setMargin(0)
        if child is not None:
            child.setParent(self)
            layout.addWidget(child, 1, Qt.AlignHCenter)
        self.resize(parent.size())
        parent.installEventFilter(self)
    
    def __del__(self):
        self.parent().removeEventFilter(self)
        if self.originallyFocused is not None:
            self.originallyFocused.setFocus(Qt.OtherFocusReason)
    
    def mousePressEvent(self, e):
        # clicking hides it
        self.deleteLater()
    
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.deleteLater()
        else:
            QWidget.keyPressEvent(self, e)
    
    def showEvent(self, e):
        self.originallyFocused = QApplication.focusWidget()
        if self.child is not None:
            self.child.setFocus(Qt.OtherFocusReason)
        else:
            self.setFocus(Qt.OtherFocusReason)
    
    def eventFilter(self, o, e):
        if e.type() == QEvent.Resize:
            self.resize(e.size())
            print self.child.size()
        return QWidget.eventFilter(self, o, e)


class SearchPanel(QWidget):
    shadowColor = QColor(150, 150, 150, 200)
    shadowWidth = 7
    def __init__(self, parent, view, structure):
        QWidget.__init__(self, parent)
        self.view = view
        self.structure = structure[:]
        f = self.font()
        fontSize = QFontInfo(f).pixelSize()
        self.setFixedWidth(fontSize * 30)
        layout = QHBoxLayout(self)
        vbox = QVBoxLayout()
        layout.addSpacing(10)
        layout.addLayout(vbox, 1)
        layout.addSpacing(10)
        self.filterBox = KLineEdit(self)
        self.connect(self.filterBox, SIGNAL('textChanged(const QString &)'), self.filterText)
        self.connect(self.filterBox, SIGNAL('returnPressed()'), self.jumpToFirstItem)
        self.filterBox.setClearButtonShown(True)
        self.setFocusProxy(self.filterBox)
        vbox.addWidget(self.filterBox, 0, Qt.AlignTop)
        self.symbolList = QListWidget(self)
        self.symbolList.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.connect(self.symbolList, SIGNAL('activated(const QModelIndex &)'), self.itemActivated)
        vbox.addWidget(self.symbolList)
        self.items = []
        for item in self.structure:
            x = QListWidgetItem(item.longName)
            self.items.append(x)
            self.symbolList.addItem(x)
    
    def keyPressEvent(self, e):
        if self.items:
            if e.key() == Qt.Key_Down:
                self.symbolList.setCurrentItem(self.items[self.firstVisibleItem()])
                self.symbolList.setFocus(Qt.OtherFocusReason)
            elif e.key() == Qt.Key_Up:
                self.symbolList.setCurrentItem(self.items[self.lastVisibleItem()])
                self.symbolList.setFocus(Qt.OtherFocusReason)
        QWidget.keyPressEvent(self, e)
    
    def filterText(self, t):
        ''' case insensitive filtering of the list '''
        t = unicode(t).lower()
        # print self.structure
        for i, item in enumerate(self.structure):
            self.items[i].setHidden(t not in item.longName.lower())
    
    def jumpToFirstItem(self):
        if self.structure:
            goToLine(self.view, self.structure[self.firstVisibleItem()].line)
            # close
            self.parent().deleteLater()
    
    def itemActivated(self, index):
        goToLine(self.view, self.structure[index.row()].line)
        self.parent().deleteLater()
    
    def firstVisibleItem(self):
        ''' The index of the first visible item in the symbol list '''
        for i, item in enumerate(self.items):
            if not item.isHidden():
                return i
    
    def lastVisibleItem(self):
        ''' The index of the last visible item in the symbol list '''
        for i, item in enumerate(reversed(self.items)):
            if not item.isHidden():
                return len(self.items) - 1 - i
        
    
    def paintEvent(self, e):
        p = QPainter(self)
        leftRect = QRect(0, 2, self.shadowWidth, self.height() - 2)
        rightRect = QRect(self.width() - self.shadowWidth, 2, self.shadowWidth, self.height() - 2)
        centerRect = QRect(leftRect.width(), leftRect.topLeft().y(), rightRect.topLeft().x() - leftRect.width(), leftRect.bottomLeft().y())
        
        shadowEndColor = QColor(self.shadowColor)
        shadowEndColor.setAlpha(0)
        
        # print shadowEndColor.getRgb()
        # print self.shadowColor.getRgb()
        leftGradient = QLinearGradient(QPointF(leftRect.topLeft()), QPointF(leftRect.topRight()))
        leftGradient.setColorAt(0, shadowEndColor)
        leftGradient.setColorAt(1, self.shadowColor)
        
        # print rightRect.topLeft(), rightRect.topRight()
        rightGradient = QLinearGradient(QPointF(rightRect.topLeft()), QPointF(rightRect.topRight()))
        rightGradient.setColorAt(0, self.shadowColor)
        rightGradient.setColorAt(1, shadowEndColor)
        
        p.fillRect(leftRect, QBrush(leftGradient))
        p.fillRect(rightRect, QBrush(rightGradient))
        p.fillRect(centerRect, QColor(240, 245, 255, 200))
        


# the singleton instance of the structure widget that's used. This is
# added to the Kate sidebar on init.
sidebar = SourceStructureWidget()
# the structure of the webpage
structure = []
# kate.viewChanged()

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
    # Human = Class(30, 'Human')
    # sidebar.setStructure([
        # GlobalVariable(3, '__name__'),
        # GlobalVariable(4, '__author__'),
        # Function(6, 'print(string, end=\'\\n\')'),
        # Function(10, 'exit()'),
        # Human,
        # Method(31, '__init__(self)'),
        # Method(35, '__del__(self)'),
        # Method(38, 'setName(self, name)'),
        # Method(45, 'sayMyName(self)'),
    # ])

@kate.unload
def removeSidebar():
    global sidebar
    if kate.objectIsAlive(sidebar):
        sidebar.setParent(None)
    sidebar = None


@kate.viewChanged
def viewChanged():
    sidebar.viewChanged()

@kate.action('Symbol Jump', icon='bookmarks-organize', shortcut='Ctrl+;', menu='View')
def showSymbolFilter():
    view = kate.activeView()
    panel = SearchPanel(None, view, structure[:])
    screen = WidgetScreen(view, child=panel)
    screen.show()
    # print 'hey'


def verticalGradient(top, bottom):
    g = QLinearGradient(0, 0, 0, SourceList.ItemHeight)
    # g.setCoordinateMode(QGradient.StretchToDeviceMode)
    g.setColorAt(0, QColor(top))
    g.setColorAt(1, QColor(bottom))
    return QBrush(g)

def setBackgroundColor(widget, color):
    ''' Utility function to set the background color of a QWidget '''
    p = widget.palette()
    p.setColor(QPalette.Active, QPalette.Window, color)
    p.setColor(QPalette.Inactive, QPalette.Window, color)
    widget.setPalette(p)
    widget.setAutoFillBackground(True)
    
def goToLine(view, line):
    ''' Moves the view's cursor to the end of the given line '''
    cursor = view.cursorPosition()
    lineLength = len(unicode(view.document().line(line)))
    view.setCursorPosition(KTextEditor.Cursor(line, lineLength))
    kate.centralWidget().setFocus(Qt.OtherFocusReason)
