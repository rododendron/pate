
#include "Python.h"

#include <QApplication>
#include <QLibrary>
#include <QStack>
#include <QDir>
#include <QFileInfo>
#include <QFile>

#include <kglobal.h>
#include <kconfig.h>
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
#define THREADED 0


static PyObject *pate_saveConfiguration(PyObject *self) {
    if(Pate::Engine::self()->isInitialised())
        Pate::Engine::self()->saveConfiguration();
    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef pateMethods[] = {
    {"saveConfiguration", (PyCFunction) pate_saveConfiguration, METH_NOARGS, NULL},
    {NULL, NULL, 0, NULL}
};

Pate::Engine* Pate::Engine::m_self = 0;

Pate::Engine::Engine(QObject *parent) : QObject(parent) {
    m_initialised = false;
    m_pythonLibrary = 0;
    m_pluginsLoaded = false;
    m_configuration = PyDict_New();
    reloadConfiguration();
}

Pate::Engine::~Engine() {
    // shut the interpreter down if it has been started
    
//     if(m_configuration) {
//         saveConfiguration();
//         Py_DECREF(m_configuration);
//         m_configuration = 0;
//     }
    if(m_initialised) {
        kDebug() << "Unloading m_pythonLibrary...";
        kDebug() << m_pythonLibrary->unload();
        delete m_pythonLibrary;
    }
}

Pate::Engine* Pate::Engine::self() {
    if(!m_self) {
        m_self = new Pate::Engine(qApp);
    }
    return m_self;
}

void Pate::Engine::del() {
    kDebug() << "delete called";
    if(!m_self)
        return;
    if(m_self->isInitialised()) {
        kDebug() << "initialised, acquiring state...";
#if THREADED
        PyEval_AcquireThread(m_self->m_pythonThreadState);
#endif
        kDebug() << "state acquired. Calling _pluginsUnloaded..";
        kDebug() << "Ok";
        kDebug() << "Finalising...";
        Py_Finalize();
        kDebug() << "Finalised.";
    }
    delete m_self;
    kDebug() << "deleted self";
    m_self = 0;
}

bool Pate::Engine::isInitialised() {
    return m_initialised;
}

bool Pate::Engine::init() {
    if(m_initialised)
        return true;
//     kDebug() << "Creating m_pythonLibrary";
    m_pythonLibrary = new QLibrary(PATE_PYTHON_LIBRARY, this);
    m_pythonLibrary->setLoadHints(QLibrary::ExportExternalSymbolsHint);
//     kDebug() << "Caling m_pythonLibrary->load()..";
    if(!m_pythonLibrary->load()) {
        std::cerr << "Could not load " << PATE_PYTHON_LIBRARY << "\n";
        return false;
    }
//     kDebug() << "success!";
//     kDebug() << "Calling Py_Initialize and PyEval_InitThreads...";
    Py_Initialize();
#if THREADED
    PyEval_InitThreads();
#endif
//     kDebug() << "success!";
    // initialise our built-in module and import it
//     kDebug() << "Initting built-in module and importting...";
    Py_InitModule(PATE_MODULE_NAME, pateMethods);
    PyObject *pate = PyImport_ImportModule(PATE_MODULE_NAME);
//     kDebug() << "success!";
    PyObject *pateModuleDictionary = PyModule_GetDict(pate);
    // host the configuration dictionary
    PyDict_SetItemString(pateModuleDictionary, "configuration", m_configuration);
    // load the kate module, but find it first, and verify it loads
    QString katePackageDirectory = KStandardDirs::locate("appdata", "plugins/pate/");
    PyObject *sysPath = PyDict_GetItemString(PyModule_GetDict(PyImport_ImportModule("sys")), "path");
    Py::appendStringToList(sysPath, katePackageDirectory);
//     kDebug() << "Importing Kate...";
    PyObject *katePackage = PyImport_ImportModule("kate");
    if(!katePackage) {
        Py::traceback("Could not import the kate module. Dieing.");
        del();
        return false;
    }
//     kDebug() << "success!";
    m_initialised = true;
    reloadConfiguration();
#if THREADED
    m_pythonThreadState = PyGILState_GetThisThreadState();
    PyEval_ReleaseThread(m_pythonThreadState);
#endif
    return true;
}

void Pate::Engine::saveConfiguration() {
    if(!m_configuration || !m_initialised)
        return;
    KConfig config("paterc", KConfig::SimpleConfig);
    Py::updateConfigurationFromDictionary(&config, m_configuration);
    config.sync();
}
void Pate::Engine::reloadConfiguration() {
    if(!m_initialised)
        return;
    PyDict_Clear(m_configuration);
    KConfig config("paterc", KConfig::SimpleConfig);
    Py::updateDictionaryFromConfiguration(m_configuration, &config);
}

// void Pate::Engine::die() {
//     PyEval_AcquireThread(m_pythonThreadState);
//     Py_Finalize();
//     // unload the library from memory
//     m_pythonLibrary->unload();
//     m_pythonLibrary = 0;
//     m_pluginsLoaded = false;
//     m_initialised = false;
//     kDebug() << "Pate::Engine::die() finished\n";
// }

void Pate::Engine::loadPlugins() {
    if(m_pluginsLoaded)
        return;
    init();

#if THREADED
    PyGILState_STATE state = PyGILState_Ensure();
#endif

    PyObject *pate = PyImport_ImportModule(PATE_MODULE_NAME);
    PyObject *pateModuleDictionary = PyModule_GetDict(pate);
    // find plugins and load them.
    findAndLoadPlugins(pateModuleDictionary);
    m_pluginsLoaded = true;
    PyObject *func = PyDict_GetItemString(moduleDictionary(), "_pluginsLoaded");
    if(!func) {
        kDebug() << "No " << PATE_MODULE_NAME << "._pluginsLoaded set";
    }
    // everything is loaded and started. Call the module's init callback
    else if(!Py::call(func)) {
        std::cerr << "Could not call " << PATE_MODULE_NAME << "._pluginsLoaded().";
    }
#if THREADED
    PyGILState_Release(state);
#endif
}

void Pate::Engine::unloadPlugins() {
    // We don't have the luxury of being able to unload Python easily while
    // Kate is running. If anyone can find a way, feel free to tell me and
    // I'll patch it in. Calling Py_Finalize crashes.
    // So, clean up the best that we can.
    if(!m_pluginsLoaded)
        return;
    kDebug() << "unloading";
#if THREADED
    PyGILState_STATE state = PyGILState_Ensure();
#endif
    PyObject *dict = moduleDictionary();
    PyObject *func = PyDict_GetItemString(dict, "_pluginsUnloaded");
    if(!func) {
        kDebug() << "No " << PATE_MODULE_NAME << "._pluginsUnloaded set";
    }
    else {
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
    }
#if THREADED
    PyGILState_Release(state);
#endif

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
                QString pluginPath = path+"/"+path.section('/', -1)+".py";
                QFile f(pluginPath);
                if(f.exists()) {
                    PyObject *d = Py::unicode(path);
                    PyList_Insert(pythonPath, 0, d);
                    Py_DECREF(d);
                    path = pluginPath;
                }
            }

            if(path.endsWith(".py")) {
                kDebug() << "Loading" << path;
                // import and add to pate.plugins
                QString pluginName = path.section('/', -1).section('.', 0, 0);
                PyObject *plugin = PyImport_ImportModule(PQ(pluginName));
                if(plugin) {
                    PyList_Append(plugins, plugin);
                    Py_DECREF(plugin);
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

void Pate::Engine::callModuleFunction(const QString &name) {
#if THREADED
    PyGILState_STATE state = PyGILState_Ensure();
#endif
    PyObject *dict = moduleDictionary();
    PyObject *func = PyDict_GetItemString(dict, PQ(name));
    if(!Py::call(func))
        kDebug() << "Could not call " << PATE_MODULE_NAME << "." << name << "().";    
#if THREADED
    PyGILState_Release(state);
#endif
}

#include "engine.moc"

// kate: space-indent on;
