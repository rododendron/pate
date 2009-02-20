
''' Kate module. '''

import sys
import os
import traceback
import functools

import pate
import kate.gui

from PyQt4 import QtCore, QtGui
from PyKDE4 import kdecore, kdeui
# kate namespace
from PyKDE4.kate import Kate
from PyKDE4.ktexteditor import KTextEditor

plugins = None
pluginDirectories = None

initialized = False


# Plugin API

# Configuration

class Configuration:
    ''' Configuration objects provide a configuration dictionary that is
    plugin-specific -- that is, each plugin uses kate.configuration and the
    class automatically creates a plugin-specific dictionary to it.
    
    The config is saved and loaded from disk automatically for minimal user hassle.
    Just go ahead and use kate.configuration as a persistent dictionary.
    Do not instantiate your own Configuration object; use kate.configuration instead.
    
    Any atomic Python type that is self evaulating can be used as keys or values --
    dictionaries, lists, numbers, strings, sets, and so on. '''
    sep = ':'
    def __init__(self, root):
        self.root = root
    
    def __getitem__(self, key):
        plugin = sys._getframe(1).f_globals['__name__']
        return self.root.get(plugin, {})[key]
    
    def __setitem__(self, key, value):
        plugin = sys._getframe(1).f_globals['__name__']
        if plugin not in self.root:
            self.root[plugin] = {}
        self.root[plugin][key] = value
    
    def __delitem__(self, key):
        plugin = sys._getframe(1).f_globals['__name__']
        del self.root.get(plugin, {})[key]
    
    def __contains__(self, key):
        plugin = sys._getframe(1).f_globals['__name__']
        return key in self.root.get(plugin, {})
    
    def __len__(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return len(self.root.get(plugin, {}))
    
    def __iter__(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return iter(self.root.get(plugin, {}))
    
    def __str__(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return str(self.root.get(plugin, {}))
        
    def __repr__(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return repr(self.root.get(plugin, {}))
    
    def keys(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return self.root.get(plugin, {}).keys()
    
    def values(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return self.root.get(plugin, {}).values()
    
    def items(self):
        plugin = sys._getframe(1).f_globals['__name__']
        return self.root.get(plugin, {}).items()
    
    def get(self, key, default=None):
        plugin = sys._getframe(1).f_globals['__name__']
        try:
            return self[plugin][key]
        except KeyError:
            return default
    
    def pop(self, key):
        value = self[key]
        del self[key]
        return value
    
    def save(self):
        pate.saveConfiguration()
    
    def _name(self):
        return sys._getframe(1).f_globals['__name__']

# a configuration shared by all plugins. This can also be used to
# access plugin-specific configurations
globalConfiguration = pate.configuration
# a plugin-specific configuration
configuration = Configuration(pate.configuration)


def _callAll(l, *args, **kwargs):
    for f in l:
        try:
            f(*args, **kwargs)
        except:
            traceback.print_exc()
            sys.stderr.write('\n')
            continue

def _attribute(**attributes):
    # utility decorator that we wrap events in. Simply initialises
    # attributes on the function object to make code nicer.
    def decorator(func):
        for key, value in attributes.items():
            setattr(func, key, value)
        return func
    return decorator

def _simpleEventListener(func):
    # automates the most common decorator pattern: calling a bunch
    # of functions when an event has occured
    func.functions = set()
    func.fire = functools.partial(_callAll, func.functions)
    func.clear = func.functions.clear
    return func

# Decorator event listeners

@_simpleEventListener
def init(func):
    ''' The function will be called when Kate has loaded completely: when all
    other enabled plugins have been loaded into memory, the configuration has
    been initiated, etc. '''
    init.functions.add(func)
    return func

@_simpleEventListener
def unload(func):
    ''' The function will be called when Pate is being unloaded from memory.
    Clean up any widgets that you have added to the interface (toolviews
    etc). '''
    unload.functions.add(func)
    return func

@_simpleEventListener
def viewChanged(func):
    ''' Calls the function when the view changes. To access the new active view,
    use kate.activeView() '''
    viewChanged.functions.add(func)
    return func

@_simpleEventListener
def viewCreated(func):
    ''' Calls the function when a new view is created, passing the view as a
    parameter '''
    viewCreated.functions.add(func)
    return func

@_attribute(actions=set())
def action(text, icon=None, shortcut=None, menu=None):
    ''' Decorator that adds an action to the menu bar. When the item is fired,
    your function is called. Optional shortcuts, menu to place the action in,
    and icon can be specified.
    Parameters:
        * text - The text associated with the action (used as the menu item
                 label, etc).
        * shortcut - The shortcut to fire this action or None if there is no
                     shortcut. Must be a string such as 'Ctrl+1' or a 
                     QKeySequence instance. By default no shortcut is set (by
                     passing None)
        * icon - An icon to associate with this action. It is shown alongside
                 text in the menu bar and in toolbars as required. Pass a 
                 string to use KDE's image loading system or a QPixmap or
                 QIcon to use any custom icon. None (the default) sets no icon.
        * menu - The menu under which to place this item. Must be a string 
                 such as 'tools' or 'settings', or None to not place it in any
                 menu. '''
    def decorator(func):
        a = kdeui.KAction(text, None)
        if shortcut is not None:
            if isinstance(shortcut, basestring):
                a.setShortcut(QtGui.QKeySequence(shortcut))
            else:
                a.setShortcut(shortcut)
        if icon is not None:
            if isinstance(icon, basestring):
                _icon = kdeui.KIcon(icon) # takes a string parameter
            elif isinstance(icon, QtGui.QPixmap):
                _icon = QtGui.QIcon(icon)
            else:
                _icon = icon
            a.setIcon(_icon)
        a.menu = menu
        a.connect(a, QtCore.SIGNAL('triggered()'), func)
        # delay till everything has been initialised
        action.actions.add(a)
        func.action = a
        return func
    return decorator

# End decorators


# API functions and objects

''' The global Kate::Application instance '''
application = Kate.application()

''' The global document manager for this Kate application '''
documentManager = application.documentManager()

def mainWindow():
    ''' The QWidget-derived main Kate window currently showing. A
    shortcut around kate.application.activeMainWindow().window().
    
    The Kate API differentiates between the interface main window and
    the actual widget main window. If you need to access the
    Kate.MainWindow for the methods it provides (e.g createToolView),
    then use the mainInterfaceWindow function '''
    return application.activeMainWindow().window()

def mainInterfaceWindow():
    ''' The interface to the main window currently showing. Calling
    window() on the interface window gives you the actual
    QWidget-derived main window, which is what the mainWindow()
    function returns '''
    return application.activeMainWindow()

def activeView():
    ''' The currently active view. Access its KTextEditor.Document
    by calling document() on it (or by using kate.activeDocument()).
    This is a shortcut for kate.application.activeMainWindow().activeView()'''
    return application.activeMainWindow().activeView()

def activeDocument():
    ''' The document for the currently active view '''
    return activeView().document()

def centralWidget():
    ''' The central widget that holds the tab bar and the editor.
    This is a shortcut for kate.application.activeMainWindow().centralWidget() '''
    return application.activeMainWindow().centralWidget()

def focusEditor():
    ''' Give the editing section focus '''
    print 'dumping tree....'
    for x in mainWindow().findChildren(QtGui.QWidget):
        print x.__class__.__name__, x.objectName()

def applicationDirectories(*path):
    path = os.path.join('pate', *path)
    return map(unicode, kdecore.KGlobal.dirs().findDirs("appdata", path))

def sessionConfiguration():
    if plugins is not None:
        return pate.sessionConfiguration

def objectIsAlive(obj):
    ''' Test whether an object is alive; that is, whether the pointer
    to the object still exists. '''
    import sip
    try:
       sip.unwrapinstance(obj)
    except RuntimeError:
       return False
    return True


# Initialisation

def pateInit():
    global plugins, pluginDirectories
    plugins = pate.plugins
    pluginDirectories = pate.pluginDirectories
    # wait for the configuration to be read
    def _initPhase2():
        global initialized
        initialized = True
        # set up actions -- plug them into the window's action collection
        windowInterface = application.activeMainWindow()
        window = windowInterface.window()
        nameToMenu = {} # e.g "help": KMenu
        for menu in window.findChildren(QtGui.QMenu):
            name = str(menu.objectName())
            if name:
                nameToMenu[name] = menu
        collection = window.actionCollection()
        for a in action.actions:
            # allow a configurable name so that built-in actions can be
            # overriden?
            collection.addAction(a.text(), a)
            if a.menu is not None:
                # '&Blah' => 'blah'
                menuName = a.menu.lower().replace('&', '')
                # create the menu if it doesn't exist
                if menuName not in nameToMenu:
                    before = nameToMenu['help'].menuAction()
                    menu = QtGui.QMenu(a.menu)
                    nameToMenu[menuName] = window.menuBar().insertMenu(before, menu)
                nameToMenu[menuName].addAction(a)
        # print 'init:', Kate.application(), application.activeMainWindow()
        windowInterface.connect(windowInterface, QtCore.SIGNAL('viewChanged()'), viewChanged.fire)
        windowInterface.connect(windowInterface, QtCore.SIGNAL('viewCreated(KTextEditor::View*)'), viewCreated.fire)
        _callAll(init.functions)
    QtCore.QTimer.singleShot(0, _initPhase2)

# called by pate on initialisation
pate._pluginsLoaded = pateInit
del pateInit


def pateDie():
    # Unload actions or things will crash
    global plugins, pluginDirectories
    for a in action.actions:
        for w in a.associatedWidgets():
            w.removeAction(a)
    # clear up
    unload.fire()
    
    action.actions.clear()
    init.clear()
    unload.clear()
    viewChanged.clear()
    viewCreated.clear()
    plugins = pluginDirectories = None

    
pate._pluginsUnloaded = pateDie
del pateDie

def pateSessionInit():
    pass
    # print 'new session:', Kate.application(), application.activeMainWindow()

pate._sessionCreated = pateSessionInit
del pateSessionInit

kate.gui.loadIcon = lambda s: kdeui.KIcon(s).pixmap(32, 32)
