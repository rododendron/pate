
#include "Python.h"

#include <QApplication>
#include <QLibrary>
#include <QStack>
#include <QDir>
#include <QFileInfo>

#include <kglobal.h>
#include <kstandarddirs.h>
#include <kdebug.h>
#include <kate/application.h>

#include <iostream>

// config.h defines PATE_PYTHON_LIBRARY, the path to libpython.so
// on the build system
#include "config.h"

#include "engine.h"
#include "utilities.h"

#define PATE_MODULE_NAME "pate" 



static PyMethodDef pateMethods[] = {
    {NULL, NULL, 0, NULL}
};

Pate::Engine* Pate::Engine::m_self = 0;

Pate::Engine::Engine(QObject *parent) : QObject(parent) {
    m_initialised = false;
    m_pythonLibrary = 0;
    m_pluginsLoaded = false;
    m_configuration = PyDict_New();
}

Pate::Engine::~Engine() {
    // shut the interpreter down if it has been started
    Py_DECREF(m_configuration);
    m_configuration = 0;
    if(m_initialised) {
        die();
    }
}

Pate::Engine* Pate::Engine::self() {
    if(!m_self)
        m_self = new Pate::Engine(qApp);
    return m_self;
}

bool Pate::Engine::isInitialised() {
    return m_initialised;
}

bool Pate::Engine::init() {
    if(m_initialised)
        return true;
    m_pythonLibrary = new QLibrary(PATE_PYTHON_LIBRARY, this);
    m_pythonLibrary->setLoadHints(QLibrary::ExportExternalSymbolsHint);
    if(!m_pythonLibrary->load()) {
        std::cerr << "Could not load " << PATE_PYTHON_LIBRARY << "\n";
        return false;
    }
    Py_Initialize();
    PyEval_InitThreads();
    // initialise our built-in module and import it
    Py_InitModule(PATE_MODULE_NAME, pateMethods);
    PyObject *pate = PyImport_ImportModule(PATE_MODULE_NAME);
    PyObject *pateModuleDictionary = PyModule_GetDict(pate);
    // host the configuration dictionary
    PyDict_SetItemString(pateModuleDictionary, "configuration", m_configuration);
    // load the kate module, but find it first, and verify it loads
    QString katePackageDirectory = KStandardDirs::locate("appdata", "plugins/pate/");
    PyObject *sysPath = PyDict_GetItemString(PyModule_GetDict(PyImport_ImportModule("sys")), "path");
    Py::appendStringToList(sysPath, katePackageDirectory);
    PyObject *katePackage = PyImport_ImportModule("kate");
    if(!katePackage) {
        Py::traceback("Could not import the kate module. Dieing.");
        die();
        return false;
    }
    m_initialised = true;
    m_pythonThreadState = PyGILState_GetThisThreadState();
    PyEval_ReleaseThread(m_pythonThreadState);
    return true;
}

void Pate::Engine::die() {
    PyEval_AcquireThread(m_pythonThreadState);
    Py_Finalize();
    // unload the library from memory
    m_pythonLibrary->unload();
    m_pythonLibrary = 0;
    m_pluginsLoaded = false;
    m_initialised = false;
}

void Pate::Engine::loadPlugins() {
    if(m_pluginsLoaded)
        return;
    init();
    PyGILState_STATE state = PyGILState_Ensure();

    PyObject *pate = PyImport_ImportModule(PATE_MODULE_NAME);
    PyObject *pateModuleDictionary = PyModule_GetDict(pate);
    // find plugins and load them.
    findAndLoadPlugins(pateModuleDictionary);
    m_pluginsLoaded = true;
    PyObject *func = PyDict_GetItemString(moduleDictionary(), "_pluginsLoaded");
    if(!func) {
        kDebug() << "No " << PATE_MODULE_NAME << "._pluginsLoaded set";
        return;
    }
    // everything is loaded and started. Call the module's init callback
    if(!Py::call(func)) {
        std::cerr << "Could not call " << PATE_MODULE_NAME << "._pluginsLoaded(). Dieing..\n";
        die();
    }
    else {
        PyGILState_Release(state);
    }
}

void Pate::Engine::unloadPlugins() {
    // We don't have the luxury of being able to unload Python easily while
    // Kate is running. If anyone can find a way, feel free to tell me and
    // I'll patch it in. Calling Py_Finalize crashes.
    // So, clean up the best that we can.
    if(!m_pluginsLoaded)
        return;
    kDebug() << "unloading";
    PyGILState_STATE state = PyGILState_Ensure();

    PyObject *dict = moduleDictionary();
    PyObject *func = PyDict_GetItemString(dict, "_pluginsUnloaded");
    if(!func) {
        kDebug() << "No " << PATE_MODULE_NAME << "._pluginsUnloaded set";
        PyGILState_Release(state);
        return;
    }
    // Remove each plugin from sys.modules
    PyObject *modules = PyImport_GetModuleDict();
    PyObject *plugins = PyDict_GetItemString(dict, "plugins");
    for(Py_ssize_t i = 0, j = PyList_Size(plugins); i < j; ++i) {
        PyObject *pluginName = PyDict_GetItemString(PyModule_GetDict(PyList_GetItem(plugins, i)), "__name__");
        if(pluginName && PyDict_Contains(modules, pluginName)) {
            PyDict_DelItem(modules, pluginName);
            kDebug() << "Deleted" << PyString_AsString(pluginName) << "from sys.modules";
        }
    }
    PyDict_DelItemString(dict, "plugins");
    Py_DECREF(plugins);
    m_pluginsLoaded = false;
    if(!Py::call(func))
        std::cerr << "Could not call " << PATE_MODULE_NAME << "._pluginsUnloaded().\n";
    PyGILState_Release(state);

}

void Pate::Engine::findAndLoadPlugins(PyObject *pateModuleDictionary) {
    // add two lists to the module: pluginDirectories and plugins
    PyObject *pluginDirectories = PyList_New(0);
    Py_INCREF(pluginDirectories);
    PyDict_SetItemString(pateModuleDictionary, "pluginDirectories", pluginDirectories);
    PyObject *plugins = PyList_New(0);
    Py_INCREF(plugins);
    PyDict_SetItemString(pateModuleDictionary, "plugins", plugins);
    // get a reference to sys.path, then add the pate directory to it
    PyObject *sys = PyImport_ImportModule("sys");
    PyObject *pythonPath = PyDict_GetItemString(PyModule_GetDict(sys), "path");
    QStack<QDir> directories;
    // now, find all directories that KDE knows about like ".../share/apps/kate/pate"
    foreach(QString directory, KGlobal::dirs()->findDirs("appdata", "pate")) {
        kDebug() << "Push path" << directory;
        directories.push(QDir(directory));
    }
    while(!directories.isEmpty()) {
        QDir directory = directories.pop();
        // add to pate.pluginDirectories and to sys.path
        Py::appendStringToList(pluginDirectories, directory.path());
        PyObject *d = Py::unicode(directory.path());
        PyList_Insert(pythonPath, 0, d);
        Py_DECREF(d);
        // traverse the directory to pate.pluginDirectories and then traverse it
        QFileInfoList infoList = directory.entryInfoList(QDir::NoDotAndDotDot | QDir::Dirs | QDir::Files);
        // directories first to add the path
        foreach(QFileInfo info, infoList) {
            QString path = info.absoluteFilePath();
            if(info.isDir()) {
                directories.push(QDir(info.absoluteFilePath()));
            }
            else if(path.endsWith(".py")) {
                kDebug() << "Loading" << path;
                // import and add to pate.plugins
                QString pluginName = path.section('/', -1).section('.', 0, 0);
                PyObject *plugin = PyImport_ImportModule(PQ(pluginName));
                if(plugin) {
                    PyList_Append(plugins, plugin);
                }
                else {
                    Py::traceback(QString("Could not load plugin %1").arg(pluginName));
                }
            }
        }
//         std::cout << "found " << PQ(directory) << "\n";
    }
}

PyObject *Pate::Engine::configuration() {
    return m_configuration;
}
PyObject *Pate::Engine::moduleDictionary() {
    PyObject *pate = PyImport_ImportModule(PATE_MODULE_NAME);
    return PyModule_GetDict(pate);
}
PyObject *Pate::Engine::wrap(void *o, QString fullClassName) {
    PyObject *sip = PyImport_ImportModule("sip");
    if(!sip) {
        Py::traceback("Could not import the sip module.");
        return 0;
    }
    QString classModuleName = fullClassName.section('.', 0, -2);
    QString className = fullClassName.section('.', -1);
    PyObject *classModule = PyImport_ImportModule(classModuleName.toAscii().data());
    if(!classModule) {
        Py::traceback(QString("Could not import %1.").arg(classModuleName));
        return 0;
    }
    PyObject *classObject = PyDict_GetItemString(PyModule_GetDict(classModule), className.toAscii().data());
    if(!classObject) {
        Py::traceback(QString("Could not get item %1 from module %2").arg(className).arg(classModuleName));
        return 0;
    }
    PyObject *wrapInstance = PyDict_GetItemString(PyModule_GetDict(sip), "wrapinstance");
    PyObject *arguments = Py_BuildValue("NO", PyLong_FromVoidPtr(o), classObject);
    PyObject *result = PyObject_CallObject(wrapInstance, arguments);
    if(!result) {
        Py::traceback("failed to wrap instance");
        return 0;
    }
    return result;
}

#include "engine.moc"

// kate: space-indent on;
