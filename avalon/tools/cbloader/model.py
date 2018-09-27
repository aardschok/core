from ... import io, style
from ...vendor.Qt import QtCore
from ...vendor import qtawesome as qta

from ..projectmanager.model import (
    TreeModel,
    Node
)

from . import lib

# Lazy attribute
node_role = TreeModel.NodeRole
display_role = QtCore.Qt.DisplayRole
edit_role = QtCore.Qt.EditRole
horizontal = QtCore.Qt.Horizontal


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
        print("Refresh!")

        self.clear()
        self.beginResetModel()

        if not self._asset_id:
            self.endResetModel()
            return

        # TODO: Get visual items
        print("Going to iterate over subsets!")

        row = 0
        for subset in io.find({"type": "subset", "parent": self._asset_id}):

            last_version = io.find_one({"type": "version",
                                        "parent": subset['_id']},
                                       sort=[("name", -1)])
            if not last_version:
                # No published version for the subset
                continue
            print("Creating node for: %s" % subset["name"])
            data = subset.copy()
            data['subset'] = data['name']

            node = Node()
            node.update(data)

            self.add_child(node)

            # Set the version information)
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


class GroupByProxyModel(QtCore.QAbstractProxyModel):

    def __init__(self, groupby=1, parent=None):
        super(GroupByProxyModel, self).__init__(parent=parent)

        self.fallback_group = "subset"
        self.group_by = groupby

        self._groups = list()
        self._group_indexes = list()
        self._group_to_source_row = dict()
        self._source_row_to_group_row = list()  # can this be a set?

    def flags(self, index):
        if index.internalPointer() is None:
            return QtCore.Qt.ItemIsEnabled
        else:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def setSourceModel(self, model):
        super(GroupByProxyModel, self).setSourceModel(model)
        self.setGroupBy(self.group_by)

    def index(self, row, column, parent=QtCore.QModelIndex()):

        if parent.isValid():

            group_idx = self._group_indexes[parent.row()]
            new_index = self.createIndex(row, column, group_idx)

            return new_index

        # Note: Added check if row is in self_group_indexes
        elif column == 0 and row in self._group_indexes:
            return self._group_indexes[row]

        else:
            return self.createIndex(row, column, None)

    def parent(self, index):

        if index == QtCore.QModelIndex() or index.internalPointer() is None:
            return QtCore.QModelIndex()
        elif index.column():
            return QtCore.QModelIndex()
        else:
            return index.internalPointer()

    def mapToSource(self, index):
        # TODO: Item comes in but index.internalPointer is None, how to continue

        if index.internalPointer() is not None:

            idx = QtCore.QModelIndex(index.internalPointer()).row()
            if index.column() == 0:
                return QtCore.QModelIndex()
            if idx < 0 or idx >= self.groupCount():
                return QtCore.QModelIndex()

            grp_to_src = self._group_to_source_row[self._groups[idx]]
            source_row = grp_to_src.at(index.row())

            # Accommodate virtual column
            return self.sourceModel().index(source_row,
                                            index.column() - 1,
                                            QtCore.QModelIndex())
        else:
            return QtCore.QModelIndex()

    def mapFromSource(self, index):

        # Which group did we put this row into?
        group = self.whichGroup(index.row())
        group_idx = self._groups.index(group)

        if group_idx < 0:
            return QtCore.QModelIndex()

        # Accommodate virtual column
        index = QtCore.QModelIndex(self.createIndex(group_idx, 0, None))
        source_row = self._source_row_to_group_row[index.row()]

        return self.createIndex(source_row, index.column() + 1, index)

    def data(self, index, role=display_role):
        """This function is called constantly behind the scenes"""
        if not index.isValid():
            return

        # If we are not at column 0 or we have a parent
        if index.column() > 0:
            src_index = self.mapToSource(index)
            return self.sourceModel().data(src_index, role)

        elif index.internalPointer() is None:

            # its our group by!
            row = index.row()
            if row < self.groupCount():

                # Blank values become "(blank)"
                group = self._groups[row]
                if not group:
                    group = self.fallback_group

                # Format the group by with ride count etc
                if self.group_by != -1:
                    source_model = self.sourceModel()
                    header = source_model.headerData(self.group_by,
                                                     horizontal,
                                                     display_role)

                    count = len(self._group_to_source_row.get(header, []))
                    return_string = "%s: %s (%s)" % (header, group, count)

                else:
                    if row not in self._groups:
                        return
                    print("DATA 2")
                    count = self._groups[row].count()
                    return_string = "All %s rides" % count

                return return_string

    def headerData(self, section, orientation, role):

        if section:
            return self.sourceModel().headerData(section - 1, orientation, role)
        else:
            return "*"

    def setHeaderData(self, section,  value, orientation=horizontal,
                      role=edit_role):

        if section:
            source_model = self.sourceModel()
            s = section - 1  # Using `s` because PEP08
            return source_model.setHeaderData(s, value, orientation, role)

        return True

    def columnCount(self, parent=QtCore.QModelIndex()):
        # accommodate virtual group column
        return self.sourceModel().columnCount(parent) + 1

    def rowCount(self, parent=QtCore.QModelIndex()):

        if parent == QtCore.QModelIndex():
            return self.groupCount()

        elif parent.column() == 0 and parent.internalPointer() is None:
            grp_item = self._groups[parent.row()]
            return self._group_to_source_row[grp_item].count()

        else:
            return 0

    def hasChildren(self, index):

        if index == QtCore.QModelIndex():
            result = self.groupCount() > 0
        elif index.column() == 0 and index.internalPointer is None:
            grp_item = self._groups[index.row()]
            result = self._group_to_source_row[grp_item].count() > 0
        else:
            result = False

        return result

    def whichGroup(self, row):

        if self.group_by == -1:
            return "default"
        section = self.group_by + 1
        header_data = self.headerData(section, horizontal, display_role)

        _idx = self.sourceModel().index(row, self.group_by, parent=QtCore.QModelIndex())
        source_data = self.sourceModel().data(_idx, display_role)

        return self.groupFromValue(header_data, source_data)

    def setGroupBy(self, column):

        # Shift down
        if column >= 0:
            column -= 1

        self.group_by = column  # Accommodate virtual column

        # Debug here
        model = self.sourceModel()
        print("header: %s" % model.headerData(column, horizontal, display_role))
        print("grouping by: %s" % self.group_by)

        self.refresh()

    def groupFromValue(self, a, b):
        """
        Args
            a(str):
            b(str):
        Returns:
             str
        """
        # TODO: Fix grouping

        for key, items in self._group_to_source_row.items():
            for item in items:
                # Do some magic voodoo here
                pass

        return "default"

    def groupCount(self):
        return len(self._groups)

    def refresh(self):

        print("Setting groups")

        self.beginResetModel()
        self.clearGroups()

        source_model = self.sourceModel()

        if not source_model:
            print("No source model?")
            return

        # TODO: Ensure that row 0 gets populated as well!
        row_count = self.sourceModel().rowCount(QtCore.QModelIndex())
        print("source mode rowCount(): %s" % row_count)

        if self.group_by > 0:
            print("group by >= 0")
            for i in range(row_count):

                # Get group
                value = self.whichGroup(i)

                # Get row
                rows = self._group_to_source_row.get(value, [])
                if not rows:
                    # Add to collection of groups
                    self._group_to_source_row[value] = rows

                self._source_row_to_group_row.append(len(rows))
                rows.append(i)

        else:
            rows = list()
            for i in range(row_count):
                rows.append(i)
                self._source_row_to_group_row.append(i)

            self._group_to_source_row["default"] = rows

        # Update list of groups
        print("Updating group list!")
        print("group list: %s" % self._group_to_source_row)

        group = 0
        for key, val in self._group_to_source_row.items():
            self._groups.append(key)

            group += 1

            # TODO: Fix createIndex, it does not return an index for the model to show
            group_index = self.createIndex(group, self.group_by, None)

            print("group index", group_index)

            self._group_indexes.append(group_index)

        self.endResetModel()

    def clearGroups(self):

        self._groups = list()
        self._group_indexes = list()

        self._group_to_source_row = dict()
        self._source_row_to_group_row = list()
