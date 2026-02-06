from PyQt6.QtWidgets import (
    QTableView, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QHeaderView, QMenu, QAbstractItemView, QStyledItemDelegate,
    QApplication, QFrame,
)
from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, pyqtSignal, QMimeData,
    QUrl, QVariant, QSize,
)
from PyQt6.QtGui import QFont, QColor, QAction, QDragEnterEvent, QDropEvent

from app.models.track import Track
from app.ui.theme import (
    BG_DARKEST, BG_DARK, BG_MID, BG_LIGHT, BG_LIGHTER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED,
    ACCENT_YELLOW, ACCENT_BLUE, ACCENT_ORANGE,
    SPACING_SM, SPACING_MD,
)


COLUMNS = [
    ("#", "track_number", 40),
    ("Title", "title", 250),
    ("Artist", "artist", 150),
    ("Duration", "duration", 80),
    ("Sample Rate", "sample_rate", 100),
    ("Bit Depth", "bit_depth", 70),
    ("Ch", "channels", 40),
    ("Size", "size", 80),
]


class TrackTableModel(QAbstractTableModel):
    """Model backing the track table view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list[Track] = []

    def set_tracks(self, tracks: list[Track]):
        self.beginResetModel()
        self._tracks = list(tracks)
        self.endResetModel()

    def get_track(self, row: int) -> Track:
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def get_tracks(self) -> list[Track]:
        return list(self._tracks)

    def rowCount(self, parent=QModelIndex()):
        return len(self._tracks)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._tracks):
            return None

        track = self._tracks[index.row()]
        col_key = COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key == "track_number":
                return str(track.track_number) if track.track_number else ""
            elif col_key == "title":
                return track.display_title
            elif col_key == "artist":
                return track.artist
            elif col_key == "duration":
                return track.formatted_duration()
            elif col_key == "sample_rate":
                return track.formatted_sample_rate()
            elif col_key == "bit_depth":
                return f"{track.bit_depth}-bit" if track.bit_depth else ""
            elif col_key == "channels":
                return str(track.channels) if track.channels else ""
            elif col_key == "size":
                return track.formatted_size()

        elif role == Qt.ItemDataRole.ForegroundRole:
            if track.needs_conversion:
                return QColor(ACCENT_YELLOW)
            return QColor(TEXT_PRIMARY)

        elif role == Qt.ItemDataRole.ToolTipRole:
            if track.needs_conversion:
                return f"{track.codec.upper()} will be converted to WAV for DVD-Audio"
            return track.file_path

        elif role == Qt.ItemDataRole.UserRole:
            return track.id

        return None

    def flags(self, index: QModelIndex):
        default = super().flags(index)
        if index.isValid():
            return default | Qt.ItemFlag.ItemIsDragEnabled
        return default | Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return ["application/x-hootie-tracks", "text/uri-list"]

    def mimeData(self, indexes):
        mime = QMimeData()
        rows = sorted(set(i.row() for i in indexes if i.isValid()))
        track_ids = [self._tracks[r].id for r in rows]
        mime.setData("application/x-hootie-tracks", ",".join(track_ids).encode())
        return mime

    def move_row(self, from_row: int, to_row: int):
        if from_row == to_row or from_row < 0 or to_row < 0:
            return
        if from_row >= len(self._tracks) or to_row >= len(self._tracks):
            return
        self.beginResetModel()
        track = self._tracks.pop(from_row)
        self._tracks.insert(to_row, track)
        self.endResetModel()


class DropZoneWidget(QWidget):
    """Empty state widget shown when no tracks are loaded."""

    files_dropped = pyqtSignal(list)  # list of file paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        icon = QLabel("\u266B")
        icon.setStyleSheet(f"font-size: 48px; color: {TEXT_MUTED};")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("Drop music files here")
        title.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {TEXT_SECONDARY};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("or use the toolbar to add files")
        subtitle.setStyleSheet(f"font-size: 13px; color: {TEXT_MUTED};")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        formats = QLabel("Supports: FLAC, WAV, AIFF, MP3, OGG, OPUS, M4A")
        formats.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
        formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(formats)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"border: 2px dashed {ACCENT_BLUE}; border-radius: 12px;")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                paths.append(path)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class TrackTable(QWidget):
    """Track table with empty state drop zone."""

    files_dropped = pyqtSignal(list)
    track_selected = pyqtSignal(object)  # Track or None
    tracks_removed = pyqtSignal(list)  # list of track IDs
    tracks_moved_to_group = pyqtSignal(list, str)  # track IDs, target group ID
    track_order_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups_for_menu = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Drop zone (empty state)
        self._drop_zone = DropZoneWidget()
        self._drop_zone.files_dropped.connect(self.files_dropped.emit)

        # Table view
        self._table = QTableView()
        self._table.setAcceptDrops(True)
        self._table.setDragEnabled(True)
        self._table.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        self._model = TrackTableModel()
        self._table.setModel(self._model)

        # Column widths
        header = self._table.horizontalHeader()
        for i, (_, _, width) in enumerate(COLUMNS):
            if i == 1:  # Title column stretches
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                self._table.setColumnWidth(i, width)

        self._table.selectionModel().currentRowChanged.connect(self._on_selection_changed)

        # Handle file drops on the table
        self._table.dragEnterEvent = self._table_drag_enter
        self._table.dropEvent = self._table_drop

        layout.addWidget(self._drop_zone)
        layout.addWidget(self._table)

        self._table.hide()

    def _table_drag_enter(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls() or event.mimeData().hasFormat("application/x-hootie-tracks"):
            event.acceptProposedAction()
        else:
            QTableView.dragEnterEvent(self._table, event)

    def _table_drop(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        QTableView.dropEvent(self._table, event)

    def set_tracks(self, tracks: list[Track]):
        self._model.set_tracks(tracks)
        if tracks:
            self._drop_zone.hide()
            self._table.show()
        else:
            self._table.hide()
            self._drop_zone.show()

    def get_tracks(self) -> list[Track]:
        return self._model.get_tracks()

    def set_groups_for_context_menu(self, groups):
        self._groups_for_menu = groups

    def _on_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        if current.isValid():
            track = self._model.get_track(current.row())
            self.track_selected.emit(track)
        else:
            self.track_selected.emit(None)

    def get_selected_track_ids(self) -> list[str]:
        indexes = self._table.selectionModel().selectedRows()
        ids = []
        for idx in indexes:
            track = self._model.get_track(idx.row())
            if track:
                ids.append(track.id)
        return ids

    def _show_context_menu(self, pos):
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return

        track_ids = self.get_selected_track_ids()
        count = len(track_ids)

        menu = QMenu(self)

        # Move to group submenu
        if self._groups_for_menu:
            move_menu = QMenu(f"Move to Group", self)
            for group in self._groups_for_menu:
                action = QAction(group.name, self)
                action.triggered.connect(
                    lambda checked, gid=group.id: self.tracks_moved_to_group.emit(track_ids, gid)
                )
                move_menu.addAction(action)
            menu.addMenu(move_menu)
            menu.addSeparator()

        # Remove
        remove_action = QAction(f"Remove {count} track{'s' if count > 1 else ''}", self)
        remove_action.triggered.connect(lambda: self.tracks_removed.emit(track_ids))
        menu.addAction(remove_action)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def select_track_by_id(self, track_id: str):
        for row in range(self._model.rowCount()):
            track = self._model.get_track(row)
            if track and track.id == track_id:
                self._table.selectRow(row)
                return
