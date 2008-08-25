
''' Kate module. '''

import pate
import sys

from PyQt4 import QtCore, QtGui
# kate namespace
from PyKDE4.kate import Kate
from PyKDE4.ktexteditor import KTextEditor

plugins = None
pluginDirectories = None

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

_onInitFunctions = []

@event(functions=[])
def init(func):
    ''' The function will be called when Pate has loaded completely: when all
    other enabled plugins have been loaded into memory, the configuration has
    been initiated, etc. '''
    init.functions.append(func)
    return func



# Initialisation

def pateInit():
    global plugins, pluginDirectories
    plugins = pate.plugins
    pluginDirectories = pate.pluginDirectories
    # wait for the configuration to be read
    def _initPhase2():
        for func in init.functions:
            func()
    QtCore.QTimer.singleShot(0, _initPhase2)
# called by pate on initialisation
pate._init = pateInit
del pateInit



# Testing testing 1 2 3

@init
def foo():
    while True:
        code, success = QtGui.QInputDialog.getText(None, 'Line', 'Code:')
        if not success:
            break
        success = success
        code = str(code)
        print '> %s' % code
        try:
            eval(code)
        except SyntaxError:
            exec code
