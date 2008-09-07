
#include "plugin.h"
#include "engine.h"
#include "utilities.h"

#include <kate/application.h>
#include <kate/documentmanager.h>
#include <kate/mainwindow.h>
#include <kate/plugin.h>

#include <ktexteditor/view.h>
#include <ktexteditor/document.h>

#include <kaction.h>
#include <klocale.h>
#include <kgenericfactory.h>
#include <kconfigbase.h>
#include <kconfiggroup.h>

#include <iostream>


K_EXPORT_COMPONENT_FACTORY(pateplugin, KGenericFactory<Pate::Plugin>("pate"))

/// Plugin view, instances of which are created once for each session
Pate::PluginView::PluginView(Kate::MainWindow *window) : Kate::PluginView(window) {
}


Pate::Plugin::Plugin(QObject *parent, const QStringList &) : Kate::Plugin((Kate::Application*) parent) {
//     std::cout << "Plugin::Plugin\n";
    // initialise the Python engine
    if(!Pate::Engine::self()->init()) {
        std::cerr << TERMINAL_RED << "Could not initialise Pate. Ouch!\n" << TERMINAL_CLEAR;
    }
}

Pate::Plugin::~Plugin() {
}


Kate::PluginView *Pate::Plugin::createView(Kate::MainWindow *window) {
    return new Pate::PluginView(window);
}

/**
 * The configuration system uses one dictionary which is wrapped in Python to
 * make it appear as though it is module-specific. 
 * Atomic Python types are stored by writing their representation to the config file
 * on save and evaluating them back to a Python type on load.
 */
void Pate::Plugin::readSessionConfig(KConfigBase *config, const QString &) {
    if(!Pate::Engine::self()->isInitialised())
        return;
    if(!config->hasGroup("Pate"))
        return;
    // relatively safe evaluation environment for Pythonizing the serialised types:
    PyObject *evaluationLocals = PyDict_New();
    PyObject *evaluationGlobals = PyDict_New();
    PyObject *evaluationBuiltins = PyDict_New();
    PyDict_SetItemString(evaluationGlobals, "__builtin__", evaluationBuiltins);
    // read config values for our group, shoving the Python evaluated value into a dict
    KConfigGroup group = config->group("Pate");
    foreach(QString key, group.keyList()) {
        QString valueString = group.readEntry(key);
        PyObject *value = PyRun_String(PQ(group.readEntry(key)), Py_eval_input, evaluationLocals, evaluationGlobals);
        if(value) {
            PyObject *c = Pate::Engine::self()->configuration();
            PyDict_SetItemString(c, PQ(key), value);
        }
        else {
            Py::traceback(QString("Bad config value: %1").arg(valueString));
        }
    }
    Py_DECREF(evaluationBuiltins);
    Py_DECREF(evaluationGlobals);
    Py_DECREF(evaluationLocals);
}

void Pate::Plugin::writeSessionConfig(KConfigBase *config, const QString &) {
    // write session config data
    KConfigGroup group(config, "Pate");
    PyObject *key, *value;
    Py_ssize_t position = 0;
    while(PyDict_Next(Pate::Engine::self()->configuration(), &position, &key, &value)) {
        // ho ho
        QString keyString = PyString_AsString(key);
        PyObject *pyRepresentation = PyObject_Repr(value);
        if(!pyRepresentation) {
            Py::traceback(QString("Could not get the representation of the value for '%1'").arg(keyString));
            continue;
        }
        QString valueString = PyString_AsString(pyRepresentation);
        group.writeEntry(keyString, valueString);
        Py_DECREF(pyRepresentation);
    }
}


#include "plugin.moc"

