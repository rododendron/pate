

set(sources plugin.cpp engine.cpp utilities.cpp)

configure_file(config.h.cmake ${CMAKE_CURRENT_BINARY_DIR}/config.h)

kde4_add_plugin(pateplugin ${sources})

target_link_libraries(pateplugin ${KDE4_KDEUI_LIBS} ${PYTHON_LIBRARY} kateinterfaces)

install(TARGETS pateplugin DESTINATION ${PLUGIN_INSTALL_DIR})
install(FILES pate.desktop DESTINATION ${SERVICES_INSTALL_DIR})
install(DIRECTORY kate DESTINATION share/apps/kate/plugins/pate)
