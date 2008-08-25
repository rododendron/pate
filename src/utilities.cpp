
#include "Python.h"

#include <QString>
#include <iostream>

#include "utilities.h"


namespace Pate { namespace Py {

PyObject *unicode(const QString &string) {
    PyObject *s = PyString_FromString(PQ(string));
    PyObject *u = PyUnicode_FromEncodedObject(s, "utf-8", "strict");
    Py_DECREF(s);
    return u;
}

bool call(PyObject *function, PyObject *arguments) {
    PyObject *result = PyObject_CallObject(function, arguments);
    if(result != NULL) {
        // success
        Py_DECREF(result);
        return true;
    }
    std::cerr << TERMINAL_RED << "Py::call:\n";
    PyErr_Print();
    std::cerr << TERMINAL_CLEAR;
    return false;
}

bool call(PyObject *function) {
    // Overload: call a Python callable with no arguments
    PyObject *arguments = PyTuple_New(0);
    bool result = call(function, arguments);
    Py_DECREF(arguments);
    return result;
}

void appendStringToList(PyObject *list, const QString &value) {
    PyObject *u = unicode(value);
    PyList_Append(list, u);
    Py_DECREF(u);
}

void traceback(const QString &description) {
    std::cerr << TERMINAL_RED;
    PyErr_Print();
    std::cerr << PQ(description) << TERMINAL_CLEAR << std::endl;
}


}} // namespace Py, namespace Pate

