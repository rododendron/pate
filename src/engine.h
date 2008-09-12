
#ifndef PATE_ENGINE_H
#define PATE_ENGINE_H

#include <QObject>

#include "Python.h"

class QLibrary;


namespace Pate {

/**
 * The Engine class hosts the Python interpreter, loading
 * it into memory within Kate, and then with finding and
 * loading all of the Pate plugins. It is implemented as
 * a singleton class.
*/
class Engine : public QObject {
    Q_OBJECT
public:
    static Engine* self();
    
    /// Start the interpreter.
    bool init();
    
    /// Whether or not init() has been called and been successful
    bool isInitialised();
    
    /// The root configuration used by Python objects. It is a Python
    /// dictionary
    PyObject *configuration();
    
    /// This engine's embedded Python module's dictionary
    PyObject *moduleDictionary();
    
    /// A PyObject* for an arbitrary Qt/KDE object that has been wrapped
    /// by SIP. Nifty.
    PyObject *wrap(void *o, QString className);
    
    /// Close the interpreter and unload it from memory. Called 
    /// automatically by the destructor, so you shouldn't need it yourself
    void die();
    
    Engine(const QString &moduleName);

// signals:
//     void populateConfiguration(PyObject *configurationDictionary);

protected:
    Engine(QObject *parent);
    ~Engine();
    
    // Finds and loads Python plugins, given a PyObject module dictionary
    // to load them into
    void findAndLoadPlugins(PyObject *pateModuleDictionary);

private:
    static Engine *m_self;
    QLibrary *m_pythonLibrary;
    bool m_initialised;
    PyObject *m_configuration;
};


} // namespace Pate

#endif
