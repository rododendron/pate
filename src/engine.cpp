
#include "Python.h"

#include <QApplication>
#include <QLibrary>
#include <QDirIterator>

#include <kglobal.h>
#include <kstandarddirs.h>
#include <kate/application.h>

#include <iostream>

// config.h defines PATE_PYTHON_LIBRARY, the path to libpython.so
// on the build system
#include "config.h"

#include "engine.h"
#include "utilities.h"

#define PATE_MODULE_NAME "pate" 


static PyObject *pate__init(PyObject *self, PyObject *args) {
    std::cerr << "pate._init() called. This annoys me. Set me to something nice!\n";
    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef pateMethods[] = {
    {"_init", pate__init, METH_VARARGS, "A callback called when Pate is initialised \
    and all plugins have been loaded. Should be overriden elsewhere -- the default \
    implementation does nothing"},
    {NULL, NULL, 0, NULL}
};

Pate::Engine* Pate::Engine::m_self = 0;

Pate::Engine::Engine(QObject *parent) : QObject(parent) {
    m_initialised = false;
    m_pythonLibrary = 0;
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

void Pate::Engine::die() {
    Py_Finalize();
    // unload the library from memory
    m_pythonLibrary->unload();
    m_pythonLibrary = 0;
    m_initialised = false;
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
    // find plugins and load them. Awesome.
    findAndLoadPlugins(pateModuleDictionary);
    // everything is loaded and started. Call the module's init callback
    if(!Py::call(PyDict_GetItemString(pateModuleDictionary, "_init"))) {
        std::cerr << "Could not call " << PATE_MODULE_NAME << "._init(). Dieing..\n";
        die();
    }
    m_initialised = true;
    return true;
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
    // now, find all directories that KDE knows about like ".../share/apps/kate/pate"
    foreach(QString directory, KGlobal::dirs()->findDirs("appdata", "pate")) {
        // add the directory to pate.pluginDirectories and then traverse it
        Py::appendStringToList(pluginDirectories, directory);
        QDirIterator it(directory, QDirIterator::Subdirectories);
        while(it.hasNext()) {
            QString path = it.next();
//             std::cout << "reading " << (const char*) subdirectory.toUtf8() << "\n";
            if(path.endsWith("/..")) {
                // ooooh. Add the directory the sys.path
                path = path.left(path.size() - 3);
                PyObject *d = Py::unicode(path);
                PyList_Insert(pythonPath, 0, d);
                Py_DECREF(d);
//                 std::cout << "Added " << PQ(path) << " to el path\n";
            }
            else if(path.endsWith(".py")) {
                QString pluginName = path.section('/', -1).section('.', 0, 0);
                // apparently 2.4 takes a char* as the param to ImportModule. This
                // accounts for that.
                PyObject *plugin = PyImport_ImportModule(PY_IMPORT_NAME_CAST(PQ(pluginName)));
                if(plugin) {
                    PyList_Append(plugins, plugin);
                    std::cout << "loaded " << PQ(pluginName) << "\n";
                }
                else {
                    Py::traceback(QString("Could not load plugin ''").arg(pluginName));
                }
            }
        }
//         std::cout << "found " << PQ(directory) << "\n";
    }
}

PyObject *Pate::Engine::configuration() {
    return m_configuration;
}

#include "engine.moc"


