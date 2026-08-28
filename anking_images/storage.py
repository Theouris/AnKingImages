"""CSV-backed storage for saved image metadata."""

from __future__ import annotations

import csv
import json
import os
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .core import UNCATEGORIZED_SYSTEM, normalize_media_filename, record_id_for


CSV_COLUMNS = (
    "record_id",
    "saved_at_utc",
    "note_id",
    "card_id",
    "deck_name",
    "note_type",
    "field_names",
    "image_src",
    "media_filename",
    "alt_text",
    "image_title",
    "rendered_width",
    "rendered_height",
    "natural_width",
    "natural_height",
    "systems",
    "tags",
    "favorite",
)


def _json_list(values: Iterable[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _parse_list(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return tuple(part.strip() for part in value.split(";") if part.strip())
    if not isinstance(parsed, list):
        return ()
    return tuple(str(item) for item in parsed if str(item))


def _int(value: object) -> int:
    try:
        return int(float(str(value or 0)))
    except (TypeError, ValueError):
        return 0


def _bool(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SavedImage:
    record_id: str
    saved_at_utc: str
    note_id: int
    card_id: int
    deck_name: str = ""
    note_type: str = ""
    field_names: tuple[str, ...] = field(default_factory=tuple)
    image_src: str = ""
    media_filename: str = ""
    alt_text: str = ""
    image_title: str = ""
    rendered_width: int = 0
    rendered_height: int = 0
    natural_width: int = 0
    natural_height: int = 0
    systems: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    favorite: bool = False

    @classmethod
    def create(
        cls,
        *,
        note_id: int,
        card_id: int,
        deck_name: str,
        note_type: str,
        field_names: Iterable[str],
        image_src: str,
        media_filename: str,
        alt_text: str,
        image_title: str,
        rendered_width: int,
        rendered_height: int,
        natural_width: int,
        natural_height: int,
        systems: Iterable[str],
        tags: Iterable[str],
    ) -> "SavedImage":
        filename = normalize_media_filename(media_filename or image_src)
        return cls(
            record_id=record_id_for(note_id, filename, image_src),
            saved_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            note_id=int(note_id),
            card_id=int(card_id),
            deck_name=str(deck_name),
            note_type=str(note_type),
            field_names=tuple(
                dict.fromkeys(str(value) for value in field_names if value)
            ),
            image_src=str(image_src),
            media_filename=filename,
            alt_text=str(alt_text),
            image_title=str(image_title),
            rendered_width=_int(rendered_width),
            rendered_height=_int(rendered_height),
            natural_width=_int(natural_width),
            natural_height=_int(natural_height),
            systems=tuple(dict.fromkeys(str(value) for value in systems if value)),
            tags=tuple(dict.fromkeys(str(value) for value in tags if value)),
        )

    def to_row(self) -> dict[str, str]:
        return {
            "record_id": self.record_id,
            "saved_at_utc": self.saved_at_utc,
            "note_id": str(self.note_id),
            "card_id": str(self.card_id),
            "deck_name": self.deck_name,
            "note_type": self.note_type,
            "field_names": _json_list(self.field_names),
            "image_src": self.image_src,
            "media_filename": self.media_filename,
            "alt_text": self.alt_text,
            "image_title": self.image_title,
            "rendered_width": str(self.rendered_width),
            "rendered_height": str(self.rendered_height),
            "natural_width": str(self.natural_width),
            "natural_height": str(self.natural_height),
            "systems": _json_list(self.systems),
            "tags": _json_list(self.tags),
            "favorite": "1" if self.favorite else "0",
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "SavedImage":
        note_id = _int(row.get("note_id"))
        media_filename = normalize_media_filename(
            row.get("media_filename", "") or row.get("image_src", "")
        )
        record_id = row.get("record_id", "") or record_id_for(
            note_id, media_filename, row.get("image_src", "")
        )
        return cls(
            record_id=record_id,
            saved_at_utc=row.get("saved_at_utc", ""),
            note_id=note_id,
            card_id=_int(row.get("card_id")),
            deck_name=row.get("deck_name", ""),
            note_type=row.get("note_type", ""),
            field_names=_parse_list(row.get("field_names", "")),
            image_src=row.get("image_src", ""),
            media_filename=media_filename,
            alt_text=row.get("alt_text", ""),
            image_title=row.get("image_title", ""),
            rendered_width=_int(row.get("rendered_width")),
            rendered_height=_int(row.get("rendered_height")),
            natural_width=_int(row.get("natural_width")),
            natural_height=_int(row.get("natural_height")),
            systems=_parse_list(row.get("systems", "")),
            tags=_parse_list(row.get("tags", "")),
            favorite=_bool(row.get("favorite", "")),
        )


class SavedImageStore:
    """Thread-safe CSV store with atomic replacement on every change."""

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = Path(csv_path)
        self._lock = threading.RLock()
        self._records: dict[str, SavedImage] = {}
        self.load_errors: list[str] = []
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            records: dict[str, SavedImage] = {}
            errors: list[str] = []
            if self.csv_path.exists() and self.csv_path.stat().st_size:
                try:
                    with self.csv_path.open(
                        "r", encoding="utf-8-sig", newline=""
                    ) as handle:
                        for line_number, row in enumerate(
                            csv.DictReader(handle), start=2
                        ):
                            try:
                                record = SavedImage.from_row(row)
                                if record.note_id and (
                                    record.media_filename or record.image_src
                                ):
                                    records[record.record_id] = record
                            except Exception as error:
                                errors.append(f"row {line_number}: {error}")
                except (OSError, csv.Error) as error:
                    errors.append(str(error))
            self._records = records
            self.load_errors = errors
            if not self.csv_path.exists():
                self._write_locked()

    def all(self) -> list[SavedImage]:
        with self._lock:
            return sorted(
                self._records.values(),
                key=lambda record: (
                    record.saved_at_utc,
                    record.media_filename.casefold(),
                ),
                reverse=True,
            )

    def is_saved(self, note_id: int, media_filename: str, image_src: str = "") -> bool:
        key = record_id_for(note_id, media_filename, image_src)
        with self._lock:
            return key in self._records

    def saved_media_for_note(self, note_id: int) -> set[str]:
        with self._lock:
            return {
                record.media_filename
                for record in self._records.values()
                if record.note_id == int(note_id) and record.media_filename
            }

    def toggle(self, record: SavedImage) -> bool:
        """Toggle a record and return True when it is saved afterward."""

        with self._lock:
            if record.record_id in self._records:
                del self._records[record.record_id]
                saved = False
            else:
                systems = record.systems or (UNCATEGORIZED_SYSTEM,)
                self._records[record.record_id] = replace(record, systems=systems)
                saved = True
            self._write_locked()
            return saved

    def delete(self, record_id: str) -> bool:
        """Delete a saved record and return whether it previously existed."""

        with self._lock:
            if str(record_id) not in self._records:
                return False
            del self._records[str(record_id)]
            self._write_locked()
            return True

    def set_favorite(self, record_id: str, favorite: bool) -> bool:
        """Set a record's favorite state and return its state afterward."""

        with self._lock:
            key = str(record_id)
            if key not in self._records:
                raise KeyError(key)
            current = self._records[key]
            desired = bool(favorite)
            if current.favorite != desired:
                self._records[key] = replace(current, favorite=desired)
                self._write_locked()
            return desired

    def replace_all(self, records: Iterable[SavedImage]) -> None:
        """Replace the catalogue and atomically rewrite the CSV."""

        with self._lock:
            self._records = {
                record.record_id: replace(
                    record,
                    systems=record.systems or (UNCATEGORIZED_SYSTEM,),
                )
                for record in records
                if record.note_id and (record.media_filename or record.image_src)
            }
            self.load_errors = []
            self._write_locked()

    def _write_locked(self) -> None:
        temporary = self.csv_path.with_name(f".{self.csv_path.name}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=CSV_COLUMNS, extrasaction="ignore"
                )
                writer.writeheader()
                for record in sorted(
                    self._records.values(),
                    key=lambda item: (item.saved_at_utc, item.record_id),
                ):
                    writer.writerow(record.to_row())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.csv_path)
        finally:
            if temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
