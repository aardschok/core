# import os
# import sys
# import errno
# import importlib
# import contextlib

import unreal_engine as ue
from pyblish import api as pyblish

from . import lib
from ..lib import logger
from .. import api, io, schema
# from ..vendor import six
# from ..vendor.Qt import QtCore, QtWidgets


class Creator(api.Creator):
    def process(self):
        nodes = list()

        if (self.options or {}).get("useSelection"):
            nodes = ue.editor_get_selected_actors()

        # TODO: enginere a way to create a data node which can contain items
        # instance = ue.
        # lib.imprint(instance, self.data)

class Loader(api.Loader):
    def __init__(self, context):
        super(Loader, self).__init__(context)
        self.fname = self.fname.replace(
            api.registered_root(), "$AVALON_PROJECTS"
        )


def create(name, asset, family, options=None, data=None):
    """Create a new instance

    Associate nodes with a subset and family. These nodes are later
    validated, according to their `family`, and integrated into the
    shared environment, relative their `subset`.

    Data relative each family, along with default data, are imprinted
    into the resulting objectSet. This data is later used by extractors
    and finally asset browsers to help identify the origin of the asset.

    Arguments:
        name (str): Name of subset
        asset (str): Name of asset
        family (str): Name of family
        options (dict, optional): Additional options from GUI
        data (dict, optional): Additional data from GUI

    Raises:
        NameError on `subset` already exists
        KeyError on invalid dynamic property
        RuntimeError on host error

    Returns:
        Name of instance

    """

    plugins = list()
    for Plugin in api.discover(api.Creator):
        has_family = family == Plugin.family

        if not has_family:
            continue

        Plugin.log.info(
            "Creating '%s' with '%s'" % (name, Plugin.__name__)
        )

        try:
            plugin = Plugin(name, asset, options, data)

            with lib.maintained_selection():
                instance = plugin.process()
        except Exception as e:
            logger.info("WARNING: %s" % e)
            continue

        plugins.append(plugin)

    assert plugins, "No Creator plug-ins were run, this is a bug"
    return instance