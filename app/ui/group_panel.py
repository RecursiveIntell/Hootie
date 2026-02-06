from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMenu, QInputDialog, QFrame,
    QAbstractItemView, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QSize
from PyQt6.QtGui import QFont, QColor, QAction, QDrag

from app.models.group import Group
from app.models.project import MAX_GROUPS
from app.ui.theme import (
    BG_DARK, BG_MID, BG_LIGHT, BG_LIGHTER, TEXT_PRIMARY, TEXT_SECONDARY,
    TEXT_MUTED, ACCENT_BLUE, ACCENT_ORANGE, GROUP_COLORS,
    SPACING_SM, SPACING_MD, SPACING_LG,
)


ALL_TRACKS_ID = "__all__"


class GroupItemWidget(QFrame):
    """Custom widget for a group list item."""

    def __init__(self, group: Group, parent=None):
        super().__init__(parent)
        self.group = group
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Color dot
        self._color_dot = QLabel()
        self._color_dot.setFixedSize(10, 10)
        self._color_dot.setStyleSheet(
            f"background-color: {group.color_tag}; "
            f"border-radius: 5px; border: none;"
        )
        layout.addWidget(self._color_dot)

        # Name and info
        info = QVBoxLayout()
        info.setSpacing(0)

        self._name_label = QLabel(group.name)
        self._name_label.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {TEXT_PRIMARY};")
        info.addWidget(self._name_label)

        self._info_label = QLabel()
        self._info_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        info.addWidget(self._info_label)

        layout.addLayout(info, 1)

        self.update_info()

    def update_info(self):
        count = self.group.track_count
        dur = self.group.formatted_duration()
        self._info_label.setText(f"{count} track{'s' if count != 1 else ''}  \u00B7  {dur}")
        self._name_label.setText(self.group.name)
        self._color_dot.setStyleSheet(
            f"background-color: {self.group.color_tag}; "
            f"border-radius: 5px; border: none;"
        )


class AllTracksWidget(QFrame):
    """Widget for the 'All Tracks' meta-item."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self._count = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        icon = QLabel("\u266B")
        icon.setFixedWidth(16)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"color: {ACCENT_ORANGE}; font-size: 14px;")
        layout.addWidget(icon)

        self._label = QLabel("All Tracks")
        self._label.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {TEXT_PRIMARY};")
        layout.addWidget(self._label, 1)

        self._count_label = QLabel("0")
        self._count_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; "
            f"background-color: {BG_LIGHTER}; border-radius: 8px; "
            f"padding: 1px 6px;"
        )
        layout.addWidget(self._count_label)

    def set_count(self, count: int):
        self._count = count
        self._count_label.setText(str(count))


class GroupPanel(QWidget):
    """Left sidebar showing project groups."""

    group_selected = pyqtSignal(str)  # group_id or ALL_TRACKS_ID
    group_renamed = pyqtSignal(str, str)  # group_id, new_name
    group_deleted = pyqtSignal(str)  # group_id
    group_added = pyqtSignal()
    group_color_changed = pyqtSignal(str, str)  # group_id, new_color
    group_reordered = pyqtSignal(list)  # ordered list of group IDs

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(280)
        self._groups: list[Group] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(f"background-color: {BG_DARK}; border-bottom: 1px solid {BG_LIGHTER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Groups")
        title.setStyleSheet(f"font-weight: 600; font-size: 11px; color: {TEXT_MUTED}; text-transform: uppercase;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        header_layout.addWidget(self._count_label)

        layout.addWidget(header)

        # List
        self._list = QListWidget()
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setStyleSheet(f"background-color: {BG_DARK};")
        self._list.setSpacing(2)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.model().rowsMoved.connect(self._on_rows_moved)

        # Accept track drops
        self._list.setAcceptDrops(True)

        layout.addWidget(self._list, 1)

        # Add group button
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: {BG_DARK}; border-top: 1px solid {BG_LIGHTER};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(8, 8, 8, 8)

        add_btn = QPushButton("+ Add Group")
        add_btn.setStyleSheet(
            f"QPushButton {{ border: 1px dashed {BG_LIGHTER}; color: {TEXT_MUTED}; "
            f"background-color: transparent; border-radius: 6px; padding: 8px; }}"
            f"QPushButton:hover {{ border-color: {ACCENT_BLUE}; color: {ACCENT_BLUE}; }}"
        )
        add_btn.clicked.connect(self.group_added.emit)
        btn_layout.addWidget(add_btn)

        layout.addWidget(btn_frame)

    def set_groups(self, groups: list[Group], total_tracks: int = 0):
        self._groups = groups
        self._refresh()
        self._update_all_tracks_count(total_tracks)

    def _refresh(self):
        current_id = self._get_selected_id()
        self._list.blockSignals(True)
        self._list.clear()

        # "All Tracks" item
        all_widget = AllTracksWidget()
        item = QListWidgetItem(self._list)
        item.setSizeHint(all_widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, ALL_TRACKS_ID)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        self._list.setItemWidget(item, all_widget)

        # Group items
        for group in self._groups:
            widget = GroupItemWidget(group)
            item = QListWidgetItem(self._list)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, group.id)
            self._list.setItemWidget(item, widget)

        # Count label
        self._count_label.setText(f"{len(self._groups)}/{MAX_GROUPS}")

        # Restore selection
        self._select_by_id(current_id or ALL_TRACKS_ID)
        self._list.blockSignals(False)

    def _update_all_tracks_count(self, count: int):
        if self._list.count() > 0:
            item = self._list.item(0)
            widget = self._list.itemWidget(item)
            if isinstance(widget, AllTracksWidget):
                widget.set_count(count)

    def update_group_info(self, total_tracks: int = 0):
        """Refresh all group item widgets and all-tracks count."""
        for i in range(1, self._list.count()):
            item = self._list.item(i)
            widget = self._list.itemWidget(item)
            if isinstance(widget, GroupItemWidget):
                widget.update_info()
        self._update_all_tracks_count(total_tracks)

    def _get_selected_id(self) -> str:
        item = self._list.currentItem()
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return ALL_TRACKS_ID

    def _select_by_id(self, group_id: str):
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == group_id:
                self._list.setCurrentRow(i)
                return
        self._list.setCurrentRow(0)

    def _on_row_changed(self, row: int):
        if row < 0:
            return
        item = self._list.item(row)
        if item:
            gid = item.data(Qt.ItemDataRole.UserRole)
            self.group_selected.emit(gid)

    def _on_rows_moved(self, *_args):
        # Rebuild group order from list, skipping "All Tracks" (index 0)
        new_order = []
        for i in range(1, self._list.count()):
            item = self._list.item(i)
            gid = item.data(Qt.ItemDataRole.UserRole)
            new_order.append(gid)
        if new_order:
            self.group_reordered.emit(new_order)

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        gid = item.data(Qt.ItemDataRole.UserRole)
        if gid == ALL_TRACKS_ID:
            return

        menu = QMenu(self)

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self._rename_group(gid))
        menu.addAction(rename_action)

        # Color submenu
        color_menu = QMenu("Change Color", self)
        for color in GROUP_COLORS:
            action = QAction(self)
            action.setText("  ")
            action.setData(color)
            pixmap_label = QLabel()
            pixmap_label.setFixedSize(16, 16)
            pixmap_label.setStyleSheet(
                f"background-color: {color}; border-radius: 3px;"
            )
            action.triggered.connect(lambda checked, c=color: self.group_color_changed.emit(gid, c))
            color_menu.addAction(action)
        menu.addMenu(color_menu)

        menu.addSeparator()

        delete_action = QAction("Delete Group", self)
        delete_action.triggered.connect(lambda: self.group_deleted.emit(gid))
        menu.addAction(delete_action)

        menu.exec(self._list.mapToGlobal(pos))

    def _rename_group(self, group_id: str):
        group = None
        for g in self._groups:
            if g.id == group_id:
                group = g
                break
        if not group:
            return
        new_name, ok = QInputDialog.getText(
            self, "Rename Group", "Group name:", text=group.name
        )
        if ok and new_name.strip():
            self.group_renamed.emit(group_id, new_name.strip())

    def select_group(self, group_id: str):
        self._select_by_id(group_id)
