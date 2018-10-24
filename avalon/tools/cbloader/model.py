from collections import defaultdict

from ... import io, api, style
from ...vendor.Qt import QtCore
from ...vendor import qtawesome as qta

from ..projectmanager.model import (
    TreeModel,
    Node
)

from . import lib


class SubsetsModel(TreeModel):
    COLUMNS = ["subset",
               "family",
               "version",
               "time",
               "author",
               "frames",
               "duration",
               "handles",
               "step"]

    def __init__(self, parent=None):
        super(SubsetsModel, self).__init__(parent=parent)
        self._asset_id = None
        self._icons = {"subset": qta.icon("fa.file-o",
                                          color=style.colors.default)}

    def set_asset(self, asset_id):
        self._asset_id = asset_id
        self.refresh()

    def setData(self, index, value, role=QtCore.Qt.EditRole):

        # Trigger additional edit when `version` column changed
        # because it also updates the information in other columns
        if index.column() == 2:
            node = index.internalPointer()
            parent = node["_id"]
            version = io.find_one({"name": value,
                                   "type": "version",
                                   "parent": parent})
            self.set_version(index, version)

        return super(SubsetsModel, self).setData(index, value, role)

    def set_version(self, index, version):
        """Update the version data of the given index.

        Arguments:
            version (dict) Version document in the database. """

        assert isinstance(index, QtCore.QModelIndex)
        if not index.isValid():
            return

        node = index.internalPointer()
        assert version['parent'] == node['_id'], ("Version does not "
                                                  "belong to subset")

        # Get the data from the version
        version_data = version.get("data", dict())

        # Compute frame ranges (if data is present)
        start = version_data.get("startFrame", None)
        end = version_data.get("endFrame", None)
        handles = version_data.get("handles", None)
        if start is not None and end is not None:
            # Remove superfluous zeros from numbers (3.0 -> 3) to improve
            # readability for most frame ranges
            start_clean = ('%f' % start).rstrip('0').rstrip('.')
            end_clean = ('%f' % end).rstrip('0').rstrip('.')
            frames = "{0}-{1}".format(start_clean, end_clean)
            duration = end - start + 1
        else:
            frames = None
            duration = None

        family = version_data.get("families", [None])[0]
        family_config = lib.get(lib.FAMILY_CONFIG, family)

        node.update({
            "version": version['name'],
            "version_document": version,
            "author": version_data.get("author", None),
            "time": version_data.get("time", None),
            "family": family,
            "familyLabel": family_config.get("label", family),
            "familyIcon": family_config.get('icon', None),
            "startFrame": start,
            "endFrame": end,
            "duration": duration,
            "handles": handles,
            "frames": frames,
            "step": version_data.get("step", None)
        })

    def refresh(self):

        self.clear()
        self.beginResetModel()
        if not self._asset_id:
            self.endResetModel()
            return

        row = 0
        for subset in io.find({"type": "subset",
                               "parent": self._asset_id}):

            last_version = io.find_one({"type": "version",
                                        "parent": subset['_id']},
                                       sort=[("name", -1)])
            if not last_version:
                # No published version for the subset
                continue

            data = subset.copy()
            data['subset'] = data['name']

            node = Node()
            node.update(data)

            self.add_child(node)

            # Set the version information
            index = self.index(row, 0, parent=QtCore.QModelIndex())
            self.set_version(index, last_version)

            row += 1

        self.endResetModel()

    def data(self, index, role):

        if not index.isValid():
            return

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 1:
                # Show familyLabel instead of family
                node = index.internalPointer()
                return node.get("familyLabel", None)

        if role == QtCore.Qt.DecorationRole:

            # Add icon to subset column
            if index.column() == 0:
                return self._icons['subset']

            # Add icon to family column
            if index.column() == 1:
                node = index.internalPointer()
                return node.get("familyIcon", None)

        return super(SubsetsModel, self).data(index, role)

    def flags(self, index):
        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        # Make the version column editable
        if index.column() == 2:  # version column
            flags |= QtCore.Qt.ItemIsEditable

        return flags


class LoaderModel(TreeModel):
    COLUMNS = ["label"]

    def __init__(self, parent=None):
        super(LoaderModel, self).__init__(parent=parent)
        self._icons = {
            "default": qta.icon("fa.download", color=style.colors.default)
        }

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        return super(LoaderModel, self).setData(index, value, role)

    def refresh(self, node=None):

        def sorter(value):
            """Sort the Loaders by their order and then their name"""
            plugin = value[0]
            return plugin.order, plugin.__name__

        self.clear()

        self.beginResetModel()
        if not node:
            self.endResetModel()
            return

        # Create look up
        available_loaders = api.discover(api.Loader)
        version_id = node['version_document']['_id']
        representations = io.find({"type": "representation",
                                   "parent": version_id})

        loaders = list()
        for representation in representations:
            _loaders = api.loaders_from_representation(available_loaders,
                                                       representation['_id'])
            for loader in _loaders:
                loaders.append((loader, representation))

        row = 0
        for loader, representation in sorted(loaders, key=sorter):

            # Label
            loader_node = Node()

            label = getattr(loader, "label", None)
            if label is None:
                label = loader.__name__

            # Add the representation as suffix
            # Get the representation for the name
            label = "{0} ({1})".format(label, representation['name'])

            loader_node.update({
                "label": label,
                "representations": representation,
                "loader": loader,
                "icon": getattr(loader, "icon", None)
            })

            self.add_child(loader_node)

            row += 1

        self.endResetModel()

    def data(self, index, role):

        if not index.isValid():
            return

        if role == QtCore.Qt.DisplayRole:
            if index.column() == 0:
                # Show familyLabel instead of family
                node = index.internalPointer()
                return node.get("label", None)

        if role == QtCore.Qt.DecorationRole:

            # Add icon
            if index.column() == 0:
                node = index.internalPointer()
                icon = node.get("icon", None)
                if icon is None:
                    return self._icons["default"]

                icon_name = "fa.%s" % icon

                return qta.icon(icon_name, color=style.colors.default)

        return super(LoaderModel, self).data(index, role)


class FamiliesFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Filters to specified families"""

    def __init__(self, *args, **kwargs):
        super(FamiliesFilterProxyModel, self).__init__(*args, **kwargs)
        self._families = set()

    def familyFilter(self):
        return self._families

    def setFamiliesFilter(self, values):
        """Set the families to include"""
        assert isinstance(values, (tuple, list, set))
        self._families = set(values)
        self.invalidateFilter()

    def filterAcceptsRow(self, row=0, parent=QtCore.QModelIndex()):

        if not self._families:
            return False

        model = self.sourceModel()
        index = model.index(row, 0, parent=parent)

        # Ensure index is valid
        if not index.isValid() or index is None:
            return True

        # Get the node data and validate
        node = model.data(index, TreeModel.NodeRole)
        family = node.get("family", None)

        if not family:
            return True

        # We want to keep the families which are not in the list
        return family in self._families
