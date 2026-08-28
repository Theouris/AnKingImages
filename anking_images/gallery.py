"""Qt gallery and image lightbox for saved images."""

from __future__ import annotations

import base64
import binascii
from collections import defaultdict
from pathlib import Path
from typing import Callable
from urllib.parse import unquote_to_bytes

from aqt import mw
from aqt.qt import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeyEvent,
    QLabel,
    QMessageBox,
    QPixmap,
    QPushButton,
    QScrollArea,
    QSize,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.utils import qconnect

from .core import UNCATEGORIZED_SYSTEM, display_system_name
from .storage import SavedImage, SavedImageStore


def _qt_enum(group: str, value: str) -> object:
    """Resolve Qt 6 scoped enums while remaining friendly to Qt 5 builds."""

    return getattr(getattr(Qt, group, Qt), value)


ALIGN_CENTER = _qt_enum("AlignmentFlag", "AlignCenter")
ASPECT_KEEP = _qt_enum("AspectRatioMode", "KeepAspectRatio")
SMOOTH = _qt_enum("TransformationMode", "SmoothTransformation")
POINTING_CURSOR = _qt_enum("CursorShape", "PointingHandCursor")
KEY_ESCAPE = _qt_enum("Key", "Key_Escape")
TOOLBUTTON_TEXT_ONLY = _qt_enum("ToolButtonStyle", "ToolButtonTextOnly")
FRAME_NO = getattr(getattr(QFrame, "Shape", QFrame), "NoFrame")
MESSAGE_YES = getattr(getattr(QMessageBox, "StandardButton", QMessageBox), "Yes")
MESSAGE_NO = getattr(getattr(QMessageBox, "StandardButton", QMessageBox), "No")


def _media_directory() -> Path | None:
    if mw.col is None:
        return None
    try:
        return Path(mw.col.media.dir())
    except Exception:
        return None


def _load_pixmap(record: SavedImage) -> QPixmap:
    media_dir = _media_directory()
    if media_dir is not None and record.media_filename:
        candidate = media_dir / record.media_filename
        if candidate.is_file():
            pixmap = QPixmap(str(candidate))
            if not pixmap.isNull():
                return pixmap

    if record.image_src.lower().startswith("data:image/"):
        try:
            header, data = record.image_src.split(",", 1)
            raw = (
                base64.b64decode(data)
                if ";base64" in header
                else unquote_to_bytes(data)
            )
            pixmap = QPixmap()
            if pixmap.loadFromData(raw):
                return pixmap
        except (ValueError, binascii.Error):
            pass
    return QPixmap()


class ClickableImageLabel(QLabel):
    def __init__(
        self, on_click: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_click = on_click
        self.setAlignment(ALIGN_CENTER)
        self.setCursor(POINTING_CURSOR)

    def mousePressEvent(self, event: object) -> None:
        self._on_click()
        super().mousePressEvent(event)  # type: ignore[arg-type]


class ImageDetailDialog(QDialog):
    def __init__(self, record: SavedImage, pixmap: QPixmap, parent: QWidget) -> None:
        super().__init__(parent)
        self.record = record
        self.original = pixmap
        self.setWindowTitle(record.media_filename or record.alt_text or "Saved image")
        self.resize(980, 760)
        self.setMinimumSize(420, 320)
        self.setSizeGripEnabled(True)
        self.zoom_factor = 1.0

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        title = QLabel(record.media_filename or "Saved image")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        controls.addWidget(title, 1)

        self.fit_button = QPushButton("Fit to Window")
        self.fit_button.setCheckable(True)
        self.fit_button.setChecked(True)
        qconnect(self.fit_button.toggled, self._refresh_image)
        controls.addWidget(self.fit_button)

        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setToolTip("Zoom out")
        qconnect(self.zoom_out_button.clicked, self._zoom_out)
        controls.addWidget(self.zoom_out_button)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setAlignment(ALIGN_CENTER)
        self.zoom_label.setMinimumWidth(52)
        controls.addWidget(self.zoom_label)

        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom in")
        qconnect(self.zoom_in_button.clicked, self._zoom_in)
        controls.addWidget(self.zoom_in_button)

        self.fullscreen_button = QPushButton("Full Screen")
        qconnect(self.fullscreen_button.clicked, self._toggle_fullscreen)
        controls.addWidget(self.fullscreen_button)

        root.addLayout(controls)

        self.image_label = QLabel()
        self.image_label.setAlignment(ALIGN_CENTER)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(ALIGN_CENTER)
        self.scroll.setWidget(self.image_label)
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("QScrollArea { background: #17191d; border: 0; }")
        root.addWidget(self.scroll, 1)

        details = self._details_text()
        if details:
            detail_label = QLabel(details)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet("color: #777; padding: 2px 4px;")
            root.addWidget(detail_label)
        self._refresh_image()

    def _details_text(self) -> str:
        parts = []
        if self.record.deck_name:
            parts.append(f"Deck: {self.record.deck_name}")
        if self.record.field_names:
            parts.append(f"Field: {', '.join(self.record.field_names)}")
        if self.record.natural_width and self.record.natural_height:
            parts.append(
                f"{self.record.natural_width} × {self.record.natural_height} px"
            )
        return "   •   ".join(parts)

    def _refresh_image(self, _checked: bool | None = None) -> None:
        if self.original.isNull():
            return
        if self.fit_button.isChecked():
            target = self.scroll.viewport().size() - QSize(20, 20)
            target.setWidth(max(target.width(), 1))
            target.setHeight(max(target.height(), 1))
            shown = self.original.scaled(target, ASPECT_KEEP, SMOOTH)
        else:
            target = QSize(
                max(round(self.original.width() * self.zoom_factor), 1),
                max(round(self.original.height() * self.zoom_factor), 1),
            )
            shown = self.original.scaled(target, ASPECT_KEEP, SMOOTH)
        self.image_label.setPixmap(shown)
        self.image_label.resize(shown.size())
        self.zoom_label.setText(
            f"{round(shown.width() / self.original.width() * 100)}%"
        )

    def _current_fit_factor(self) -> float:
        target = self.scroll.viewport().size() - QSize(20, 20)
        return max(
            min(
                max(target.width(), 1) / self.original.width(),
                max(target.height(), 1) / self.original.height(),
            ),
            0.01,
        )

    def _zoom(self, multiplier: float) -> None:
        if self.original.isNull():
            return
        if self.fit_button.isChecked():
            self.zoom_factor = self._current_fit_factor()
            self.fit_button.setChecked(False)
        self.zoom_factor = min(max(self.zoom_factor * multiplier, 0.05), 8.0)
        self._refresh_image()

    def _zoom_in(self) -> None:
        self._zoom(1.25)

    def _zoom_out(self) -> None:
        self._zoom(0.8)

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Full Screen")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("Exit Full Screen")
        self._refresh_image()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        if hasattr(self, "fit_button") and self.fit_button.isChecked():
            self._refresh_image()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == KEY_ESCAPE and self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Full Screen")
            self._refresh_image()
            event.accept()
            return
        super().keyPressEvent(event)


class ImageCard(QFrame):
    def __init__(
        self,
        record: SavedImage,
        on_delete: Callable[[SavedImage], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._on_delete = on_delete
        self.pixmap = _load_pixmap(record)
        self._detail_dialog: ImageDetailDialog | None = None
        self.setObjectName("ankingImagesCard")
        self.setFixedWidth(220)
        self.setStyleSheet(
            "#ankingImagesCard { border: 1px solid palette(mid); border-radius: 8px; "
            "background: palette(base); padding: 7px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        image = ClickableImageLabel(self._open_detail)
        image.setFixedSize(196, 150)
        if self.pixmap.isNull():
            image.setText("Image file not found")
            image.setStyleSheet(
                "background: palette(alternate-base); color: palette(mid); border-radius: 5px;"
            )
        else:
            image.setPixmap(self.pixmap.scaled(image.size(), ASPECT_KEEP, SMOOTH))
            image.setToolTip("Click to enlarge")
        layout.addWidget(image)

        filename = QLabel(record.media_filename or record.alt_text or "Saved image")
        filename.setWordWrap(True)
        filename.setAlignment(ALIGN_CENTER)
        filename.setToolTip(self._tooltip())
        filename.setStyleSheet("font-size: 12px; padding-top: 4px;")
        layout.addWidget(filename)

        actions = QHBoxLayout()
        actions.addStretch(1)
        delete_button = QPushButton("🗑︎")
        delete_button.setAccessibleName("Delete image")
        delete_button.setToolTip("Remove this entry from My Images")
        delete_button.setFixedSize(34, 30)
        delete_button.setStyleSheet(
            "QPushButton { border: 0; border-radius: 5px; background: transparent; "
            "color: #d32f2f; font: 20px sans-serif; } "
            "QPushButton:hover { background: rgba(211, 47, 47, 0.14); } "
            "QPushButton:pressed { background: rgba(211, 47, 47, 0.24); }"
        )
        qconnect(delete_button.clicked, self._delete)
        actions.addWidget(delete_button)
        layout.addLayout(actions)

    def _tooltip(self) -> str:
        fields = ", ".join(self.record.field_names) or "Unknown"
        return (
            f"Note ID: {self.record.note_id}\n"
            f"Deck: {self.record.deck_name or 'Unknown'}\n"
            f"Field: {fields}\n"
            f"Saved: {self.record.saved_at_utc}"
        )

    def _open_detail(self) -> None:
        if self.pixmap.isNull():
            return
        self._detail_dialog = ImageDetailDialog(self.record, self.pixmap, self)
        self._detail_dialog.show()

    def _delete(self) -> None:
        self._on_delete(self.record)


class CollapsibleSystemSection(QWidget):
    def __init__(
        self,
        system: str,
        records: list[SavedImage],
        on_delete: Callable[[SavedImage], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.system = system
        self.records = records
        self._on_delete = on_delete
        self._built = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(4)
        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setText(self._toggle_text(False))
        self.toggle.setToolButtonStyle(TOOLBUTTON_TEXT_ONLY)
        self.toggle.setStyleSheet(
            "QToolButton { text-align: left; font-size: 15px; font-weight: 600; "
            "padding: 10px 12px; border: 1px solid palette(mid); border-radius: 6px; "
            "background: palette(button); }"
        )
        qconnect(self.toggle.toggled, self._set_expanded)
        layout.addWidget(self.toggle)

        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(8, 8, 8, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.content.setVisible(False)
        layout.addWidget(self.content)

    def _toggle_text(self, expanded: bool) -> str:
        arrow = "▼" if expanded else "▶"
        return f"{arrow}  {display_system_name(self.system)} ({len(self.records)})"

    def _set_expanded(self, expanded: bool) -> None:
        if expanded and not self._built:
            for index, record in enumerate(self.records):
                self.grid.addWidget(
                    ImageCard(record, self._on_delete, self.content),
                    index // 4,
                    index % 4,
                )
            self.grid.setColumnStretch(4, 1)
            self._built = True
        self.toggle.setText(self._toggle_text(expanded))
        self.content.setVisible(expanded)


class GalleryDialog(QDialog):
    def __init__(self, store: SavedImageStore, parent: QWidget) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("My Images")
        self.resize(1080, 760)
        self.setMinimumSize(720, 520)
        self.setSizeGripEnabled(True)

        root = QVBoxLayout(self)
        heading = QLabel("My Images")
        heading.setStyleSheet("font-size: 24px; font-weight: 700; padding: 2px 4px 0;")
        root.addWidget(heading)
        description = QLabel(
            "Saved images are grouped by #AK_Step1_v12::^Systems tags. "
            "Open a system to view its images."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #777; padding: 0 4px 8px;")
        root.addWidget(description)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            "background: #7a3e00; color: white; border-radius: 4px; padding: 7px;"
        )
        self.error_label.hide()
        root.addWidget(self.error_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(FRAME_NO)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        self.store.reload()
        grouped: dict[str, list[SavedImage]] = defaultdict(list)
        for record in self.store.all():
            for system in record.systems or (UNCATEGORIZED_SYSTEM,):
                grouped[system].append(record)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 8, 8)
        layout.setSpacing(7)
        if not grouped:
            empty = QLabel(
                "No saved images yet. Click the ☆ beneath an image while reviewing a card."
            )
            empty.setAlignment(ALIGN_CENTER)
            empty.setWordWrap(True)
            empty.setStyleSheet("color: #777; font-size: 15px; padding: 60px 20px;")
            layout.addWidget(empty)
        else:
            for system in sorted(
                grouped, key=lambda value: display_system_name(value).casefold()
            ):
                layout.addWidget(
                    CollapsibleSystemSection(
                        system, grouped[system], self._delete_record, container
                    )
                )
        layout.addStretch(1)
        self.scroll.setWidget(container)

        if self.store.load_errors:
            self.error_label.setText(
                "Some CSV rows could not be read: "
                + "; ".join(self.store.load_errors[:3])
            )
            self.error_label.show()
        else:
            self.error_label.hide()

    def _delete_record(self, record: SavedImage) -> None:
        name = record.media_filename or record.alt_text or "this saved image"
        answer = QMessageBox.question(
            self,
            "Delete saved image",
            f'Delete "{name}" from My Images?\n\nThe original Anki media file will not be deleted.',
            MESSAGE_YES | MESSAGE_NO,
            MESSAGE_NO,
        )
        if answer != MESSAGE_YES:
            return
        try:
            self.store.delete(record.record_id)
        except OSError as error:
            self.error_label.setText(f"The image could not be deleted: {error}")
            self.error_label.show()
            return
        self.refresh()
