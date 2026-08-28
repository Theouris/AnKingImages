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
    QEvent,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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
from .theme import GALLERY_STYLESHEET


def _qt_enum(group: str, value: str) -> object:
    """Resolve Qt 6 scoped enums while remaining friendly to Qt 5 builds."""

    return getattr(getattr(Qt, group, Qt), value)


ALIGN_CENTER = _qt_enum("AlignmentFlag", "AlignCenter")
ASPECT_KEEP = _qt_enum("AspectRatioMode", "KeepAspectRatio")
SMOOTH = _qt_enum("TransformationMode", "SmoothTransformation")
POINTING_CURSOR = _qt_enum("CursorShape", "PointingHandCursor")
TOOLBUTTON_TEXT_ONLY = _qt_enum("ToolButtonStyle", "ToolButtonTextOnly")
WINDOW_MIN_MAX_BUTTONS_HINT = _qt_enum("WindowType", "WindowMinMaxButtonsHint")
NATIVE_GESTURE_EVENT = getattr(getattr(QEvent, "Type", QEvent), "NativeGesture")
ZOOM_NATIVE_GESTURE = _qt_enum("NativeGestureType", "ZoomNativeGesture")
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


class ZoomScrollArea(QScrollArea):
    def __init__(
        self, on_zoom: Callable[[float], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._on_zoom = on_zoom

    def event(self, event: object) -> bool:
        if (
            event.type() == NATIVE_GESTURE_EVENT  # type: ignore[attr-defined]
            and event.gestureType() == ZOOM_NATIVE_GESTURE  # type: ignore[attr-defined]
        ):
            self._on_zoom(float(event.value()) * 240)  # type: ignore[attr-defined]
            event.accept()  # type: ignore[attr-defined]
            return True
        return super().event(event)  # type: ignore[arg-type]

    def wheelEvent(self, event: object) -> None:
        pixel_delta = event.pixelDelta().y()  # type: ignore[attr-defined]
        angle_delta = event.angleDelta().y()  # type: ignore[attr-defined]
        delta = pixel_delta or angle_delta
        if delta:
            self._on_zoom(float(delta))
            event.accept()  # type: ignore[attr-defined]
            return
        super().wheelEvent(event)  # type: ignore[arg-type]


class ImageDetailDialog(QDialog):
    def __init__(self, record: SavedImage, pixmap: QPixmap, parent: QWidget) -> None:
        super().__init__(parent)
        self.record = record
        self.original = pixmap
        self.setObjectName("ankingImagesDetail")
        self.setStyleSheet(GALLERY_STYLESHEET)
        self.setWindowFlag(WINDOW_MIN_MAX_BUTTONS_HINT, True)
        self.setWindowTitle(record.media_filename or record.alt_text or "Saved image")
        self.resize(980, 760)
        self.setMinimumSize(420, 320)
        self.setSizeGripEnabled(True)
        self.zoom_factor = 1.0
        self.fit_mode = True

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        title = QLabel(record.media_filename or "Saved image")
        title.setObjectName("ankingImagesDetailTitle")
        controls.addWidget(title, 1)
        root.addLayout(controls)

        self.image_label = QLabel()
        self.image_label.setAlignment(ALIGN_CENTER)
        self.scroll = ZoomScrollArea(self._zoom_from_wheel)
        self.scroll.setObjectName("ankingImagesDetailScroll")
        self.scroll.setAlignment(ALIGN_CENTER)
        self.scroll.setWidget(self.image_label)
        self.scroll.setWidgetResizable(False)
        self.scroll.setToolTip("Scroll or pinch on your mousepad to zoom")
        root.addWidget(self.scroll, 1)

        details = self._details_text()
        if details:
            detail_label = QLabel(details)
            detail_label.setObjectName("ankingImagesDetails")
            detail_label.setWordWrap(True)
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
        if self.fit_mode:
            self.zoom_factor = self._current_fit_factor()
        target = QSize(
            max(round(self.original.width() * self.zoom_factor), 1),
            max(round(self.original.height() * self.zoom_factor), 1),
        )
        shown = self.original.scaled(target, ASPECT_KEEP, SMOOTH)
        self.image_label.setPixmap(shown)
        self.image_label.resize(shown.size())

    def _current_fit_factor(self) -> float:
        target = self.scroll.viewport().size() - QSize(20, 20)
        return max(
            min(
                max(target.width(), 1) / self.original.width(),
                max(target.height(), 1) / self.original.height(),
            ),
            0.01,
        )

    def _zoom_from_wheel(self, delta: float) -> None:
        if self.original.isNull():
            return
        if self.fit_mode:
            self.zoom_factor = self._current_fit_factor()
            self.fit_mode = False
        multiplier = 1.0015**delta
        self.zoom_factor = min(max(self.zoom_factor * multiplier, 0.05), 8.0)
        self._refresh_image()

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)  # type: ignore[arg-type]
        if hasattr(self, "scroll") and self.fit_mode:
            self._refresh_image()


class ImageCard(QFrame):
    def __init__(
        self,
        record: SavedImage,
        on_favorite: Callable[[SavedImage], None],
        on_delete: Callable[[SavedImage], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.record = record
        self._on_favorite = on_favorite
        self._on_delete = on_delete
        self.pixmap = _load_pixmap(record)
        self._detail_dialog: ImageDetailDialog | None = None
        self.setObjectName("ankingImagesCard")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        image = ClickableImageLabel(self._open_detail)
        image.setFixedSize(196, 150)
        if self.pixmap.isNull():
            image.setText("Image file not found")
            image.setObjectName("ankingImagesThumbnailMissing")
        else:
            image.setPixmap(self.pixmap.scaled(image.size(), ASPECT_KEEP, SMOOTH))
            image.setToolTip("Click to enlarge")
        layout.addWidget(image)

        filename = QLabel(record.media_filename or record.alt_text or "Saved image")
        filename.setObjectName("ankingImagesFilename")
        filename.setWordWrap(True)
        filename.setAlignment(ALIGN_CENTER)
        filename.setToolTip(self._tooltip())
        layout.addWidget(filename)

        actions = QHBoxLayout()
        actions.addStretch(1)
        favorite_button = QPushButton("★" if record.favorite else "☆")
        favorite_button.setObjectName("ankingImagesFavorite")
        favorite_button.setProperty("isFavorite", record.favorite)
        favorite_button.setAccessibleName(
            "Remove image from favorites"
            if record.favorite
            else "Add image to favorites"
        )
        favorite_button.setToolTip(
            "Remove from Favorites" if record.favorite else "Add to Favorites"
        )
        favorite_button.setFixedSize(38, 34)
        qconnect(favorite_button.clicked, self._favorite)
        actions.addWidget(favorite_button)

        delete_button = QPushButton("🗑️")
        delete_button.setObjectName("ankingImagesDelete")
        delete_button.setAccessibleName("Delete image")
        delete_button.setToolTip("Remove this entry from My Images")
        delete_button.setFixedSize(38, 34)
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

    def _favorite(self) -> None:
        self._on_favorite(self.record)


class CollapsibleSystemSection(QWidget):
    def __init__(
        self,
        system: str,
        records: list[SavedImage],
        on_favorite: Callable[[SavedImage], None],
        on_delete: Callable[[SavedImage], None],
        parent: QWidget | None = None,
        *,
        title: str | None = None,
        initially_expanded: bool = False,
    ) -> None:
        super().__init__(parent)
        self.system = system
        self.title = title or display_system_name(system)
        self.records = records
        self._on_favorite = on_favorite
        self._on_delete = on_delete
        self._built = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(4)
        self.toggle = QToolButton()
        self.toggle.setObjectName("ankingImagesSection")
        self.toggle.setCheckable(True)
        self.toggle.setText(self._toggle_text(False))
        self.toggle.setToolButtonStyle(TOOLBUTTON_TEXT_ONLY)
        layout.addWidget(self.toggle)

        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(8, 8, 8, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.content.setVisible(False)
        layout.addWidget(self.content)
        qconnect(self.toggle.toggled, self._set_expanded)
        self.toggle.setChecked(initially_expanded)

    def _toggle_text(self, expanded: bool) -> str:
        arrow = "▼" if expanded else "▶"
        return f"{arrow}  {self.title} ({len(self.records)})"

    def _set_expanded(self, expanded: bool) -> None:
        if expanded and not self._built:
            if self.records:
                for index, record in enumerate(self.records):
                    self.grid.addWidget(
                        ImageCard(
                            record,
                            self._on_favorite,
                            self._on_delete,
                            self.content,
                        ),
                        index // 4,
                        index % 4,
                    )
            else:
                empty = QLabel("Use the ☆ button on an image to add it here.")
                empty.setObjectName("ankingImagesEmpty")
                empty.setWordWrap(True)
                self.grid.addWidget(empty, 0, 0, 1, 4)
            self.grid.setColumnStretch(4, 1)
            self._built = True
        self.toggle.setText(self._toggle_text(expanded))
        self.content.setVisible(expanded)


class GalleryDialog(QDialog):
    def __init__(
        self,
        store: SavedImageStore,
        parent: QWidget,
        on_catalogue_changed: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self._on_catalogue_changed = on_catalogue_changed
        self.setObjectName("ankingImagesGallery")
        self.setStyleSheet(GALLERY_STYLESHEET)
        self.setWindowFlag(WINDOW_MIN_MAX_BUTTONS_HINT, True)
        self.setWindowTitle("My Images")
        self.resize(1080, 760)
        self.setMinimumSize(720, 520)
        self.setSizeGripEnabled(True)

        root = QVBoxLayout(self)
        heading = QLabel("My Images")
        heading.setObjectName("ankingImagesHeading")
        root.addWidget(heading)
        description = QLabel(
            "Saved images are grouped by #AK_Step1_v12::^Systems tags. "
            "Open a system to view its images."
        )
        description.setObjectName("ankingImagesMuted")
        description.setWordWrap(True)
        root.addWidget(description)

        self.error_label = QLabel()
        self.error_label.setObjectName("ankingImagesError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("ankingImagesGalleryScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(FRAME_NO)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def refresh(self) -> None:
        self.store.reload()
        records = self.store.all()
        grouped: dict[str, list[SavedImage]] = defaultdict(list)
        for record in records:
            for system in record.systems or (UNCATEGORIZED_SYSTEM,):
                grouped[system].append(record)
        favorites = [record for record in records if record.favorite]

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 8, 8)
        layout.setSpacing(7)
        layout.addWidget(
            CollapsibleSystemSection(
                "__favorites__",
                favorites,
                self._favorite_record,
                self._delete_record,
                container,
                title="Favorites",
                initially_expanded=bool(favorites),
            )
        )
        if not records:
            empty = QLabel(
                "No saved images yet. Click the ☆ beneath an image while reviewing a card."
            )
            empty.setObjectName("ankingImagesEmpty")
            empty.setAlignment(ALIGN_CENTER)
            empty.setWordWrap(True)
            layout.addWidget(empty)
        else:
            for system in sorted(
                grouped, key=lambda value: display_system_name(value).casefold()
            ):
                layout.addWidget(
                    CollapsibleSystemSection(
                        system,
                        grouped[system],
                        self._favorite_record,
                        self._delete_record,
                        container,
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
        self._catalogue_changed()

    def _favorite_record(self, record: SavedImage) -> None:
        try:
            self.store.set_favorite(record.record_id, not record.favorite)
        except (KeyError, OSError) as error:
            self.error_label.setText(f"The favorite could not be updated: {error}")
            self.error_label.show()
            return
        self.refresh()

    def _catalogue_changed(self) -> None:
        if not callable(self._on_catalogue_changed):
            return
        try:
            result = self._on_catalogue_changed()
        except Exception as error:
            self.error_label.setText(
                "The gallery was updated locally, but the Anki sync card could not "
                f"be updated: {error}"
            )
            self.error_label.show()
            return
        if isinstance(result, str) and result:
            self.error_label.setText(result)
            self.error_label.show()
