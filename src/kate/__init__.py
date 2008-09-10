
''' Kate module. '''

import sys
import functools

import pate

from PyQt4 import QtCore, QtGui
from PyKDE4 import kdecore, kdeui
# kate namespace
from PyKDE4.kate import Kate
from PyKDE4.ktexteditor import KTextEditor

plugins = None
pluginDirectories = None

initialized = False

# Plugin API

class Configuration:
    ''' Configuration objects provide a configuration dictionary.
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
        if plugin not in self.root.configuration:
            self.root[plugin] = {}
        self.root.configuration[plugin][key] = value
    
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
        return str(self)
    
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

# a configuration shared by all plugins. This can also be used to
# access plugin-specific configurations
globalConfiguration = pate.configuration
# a plugin-specific configuration
configuration = Configuration(pate.configuration)


def event(**attributes):
    # utility decorator that we wrap events init
    def decorator(func):
        for key, value in attributes.items():
            setattr(func, key, value)
        return func
    return decorator

# Decorator event listeners

@event(functions=set())
def init(func):
    ''' The function will be called when Pate has loaded completely: when all
    other enabled plugins have been loaded into memory, the configuration has
    been initiated, etc. '''
    init.functions.add(func)
    return func

@event(actions=set())
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
        return func
    return decorator


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
        window = application.activeMainWindow().window()
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
        # window.actionCollection().
        for func in init.functions:
            func()
    QtCore.QTimer.singleShot(0, _initPhase2)
# called by pate on initialisation
pate._init = pateInit
del pateInit


''' The global Kate::Application instance '''
application = Kate.application()

''' The global document manager for this Kate application '''
documentManager = application.documentManager()

def mainWindow():
    ''' The QWidget-derived main Kate window currently showing. A
    shortcut around kate.application.activeMainWindow().window() '''
    return application.activeMainWindow().window()

def activeView():
    ''' The currently active view. Access its KTextEditor.Document
    by calling document() on it (or by using kate.activeDocument()).
    This is a shortcut for kate.application.activeMainWindow().activeView()'''
    return application.activeMainWindow().activeView()

def activeDocument():
    ''' The document for the currently active view '''
    return activeView().document()

    

