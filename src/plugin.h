
#ifndef PATE_PLUGIN_H
#define PATE_PLUGIN_H

#include <kate/plugin.h>
#include <kate/mainwindow.h>

#include <kxmlguiclient.h>

#include "Python.h"


namespace Pate {

class Plugin : public Kate::Plugin {
    Q_OBJECT

public:
    explicit Plugin(QObject *parent = 0, const QStringList& = QStringList());
    virtual ~Plugin();
    
    Kate::PluginView *createView(Kate::MainWindow*);

    void readSessionConfig(KConfigBase *config, const QString& groupPrefix);
    void writeSessionConfig(KConfigBase *config, const QString& groupPrefix);
};

class PluginView : public Kate::PluginView {
    Q_OBJECT
public:
    PluginView(Kate::MainWindow *window);
};

} // namespace Pate

#endif
