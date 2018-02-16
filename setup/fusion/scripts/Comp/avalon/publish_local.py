import os
import sys

import avalon.api
import avalon.fusion

import pyblish_qml
import pyblish.api


def _install_fusion():

    from pyblish_qml import settings
    import pyblish_qml.host as host

    sys.stdout.write("Setting up Pyblish QML in Fusion\n")

    if settings.ContextLabel == settings.ContextLabelDefault:
        settings.ContextLabel = "Fusion"
    if settings.WindowTitle == settings.WindowTitleDefault:
        settings.WindowTitle = "Pyblish (Fusion)"


def _set_current_working_dir():
    # Set current working directory next to comp

    filename = comp.MapPath(comp.GetAttrs()["COMPS_FileName"])
    if filename and os.path.exists(filename):
        cwd = os.path.dirname(filename)
    else:
        # Fallback to Avalon projects root
        # for unsaved files.
        cwd = os.environ["AVALON_PROJECTS"]

    os.chdir(cwd)


print("Starting Pyblish setup..")

# Install avalon
avalon.api.install(avalon.fusion)

# force current working directory to NON FUSION path
# os.getcwd will return the binary folder of Fusion in this case
_set_current_working_dir()

# install fusion title
_install_fusion()

# Specify target to change collected family in Collector
pyblish.api.register_target("renderlocal")

# Run QML in modal mode so it keeps listening to the
# server in the main thread and keeps this process
# open until QML finishes.
print("Running publish_qml.show(modal=True)..")
pyblish_qml.show(modal=True)