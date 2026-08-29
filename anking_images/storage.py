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
    "subcategory",
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
    subcategory: str = ""
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
        subcategory: str | None = None,
    ) -> "SavedImage":
        filename = normalize_media_filename(media_filename or image_src)
        normalized_systems = tuple(
            dict.fromkeys(str(value) for value in systems if value)
        )
        if subcategory is None:
            subcategory = next(
                (
                    value
                    for value in normalized_systems
                    if value != UNCATEGORIZED_SYSTEM
                ),
                "",
            )
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
            systems=normalized_systems,
            tags=tuple(dict.fromkeys(str(value) for value in tags if value)),
            subcategory=str(subcategory or "").strip(),
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
            "subcategory": self.subcategory,
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
        systems = _parse_list(row.get("systems", ""))
        raw_subcategory = row.get("subcategory")
        if raw_subcategory is None:
            # CSVs created before subheadings existed retain their old gallery
            # grouping by adopting their first system as the initial subheading.
            raw_subcategory = next(
                (value for value in systems if value != UNCATEGORIZED_SYSTEM),
                "",
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
            systems=systems,
            tags=_parse_list(row.get("tags", "")),
            subcategory=str(raw_subcategory or "").strip(),
            favorite=_bool(row.get("favorite", "")),
        )


def catalogue_reference(record: SavedImage) -> str:
    """Return the image-ID portion persisted on the Anki catalogue card."""

    return record.media_filename or record.image_src


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
                                if catalogue_reference(record):
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
        del note_id
        reference = normalize_media_filename(media_filename or image_src) or image_src
        with self._lock:
            return any(
                catalogue_reference(record) == reference
                for record in self._records.values()
            )

    def saved_media_for_note(self, note_id: int) -> set[str]:
        del note_id
        with self._lock:
            return {
                record.media_filename
                for record in self._records.values()
                if record.media_filename
            }

    def toggle(self, record: SavedImage) -> bool:
        """Toggle a record and return True when it is saved afterward."""

        with self._lock:
            reference = catalogue_reference(record)
            matching_ids = [
                record_id
                for record_id, existing in self._records.items()
                if catalogue_reference(existing) == reference
            ]
            if matching_ids:
                for record_id in matching_ids:
                    del self._records[record_id]
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

    def set_subcategory(self, record_id: str, subcategory: str) -> str:
        """Move an image to a subheading and return its normalized name."""

        with self._lock:
            key = str(record_id)
            if key not in self._records:
                raise KeyError(key)
            normalized = str(subcategory or "").strip()
            current = self._records[key]
            if current.subcategory != normalized:
                self._records[key] = replace(current, subcategory=normalized)
                self._write_locked()
            return normalized

    def replace_all(self, records: Iterable[SavedImage]) -> None:
        """Replace the catalogue and atomically rewrite the CSV."""

        with self._lock:
            self._records = {
                record.record_id: replace(
                    record,
                    systems=record.systems or (UNCATEGORIZED_SYSTEM,),
                )
                for record in records
                if catalogue_reference(record)
            }
            self.load_errors = []
            self._write_locked()

    def replace_catalogue_references(self, references: Iterable[str]) -> None:
        """Mirror compact sync references while retaining local display metadata."""

        with self._lock:
            desired = list(
                dict.fromkeys(str(value).strip() for value in references if value)
            )
            local_by_reference: dict[str, SavedImage] = {}
            for record in self._records.values():
                reference = catalogue_reference(record)
                if reference and reference not in local_by_reference:
                    local_by_reference[reference] = record

            replacement: dict[str, SavedImage] = {}
            for reference in desired:
                record = local_by_reference.get(reference)
                if record is None:
                    filename = normalize_media_filename(reference)
                    record = SavedImage.create(
                        note_id=0,
                        card_id=0,
                        deck_name="",
                        note_type="",
                        field_names=[],
                        image_src=reference,
                        media_filename=filename,
                        alt_text="",
                        image_title="",
                        rendered_width=0,
                        rendered_height=0,
                        natural_width=0,
                        natural_height=0,
                        systems=[UNCATEGORIZED_SYSTEM],
                        tags=[],
                        subcategory="",
                    )
                replacement[record.record_id] = record

            self._records = replacement
            self.load_errors = []
            self._write_locked()

    def replace_catalogue_entries(
        self, entries: Iterable[tuple[str, str]]
    ) -> None:
        """Mirror image/subheading pairs while retaining rich local metadata."""

        with self._lock:
            desired: dict[str, str] = {}
            for raw_reference, raw_subcategory in entries:
                reference = str(raw_reference or "").strip()
                if reference and reference not in desired:
                    desired[reference] = str(raw_subcategory or "").strip()

            local_by_reference: dict[str, SavedImage] = {}
            for record in self._records.values():
                reference = catalogue_reference(record)
                if reference and reference not in local_by_reference:
                    local_by_reference[reference] = record

            replacement: dict[str, SavedImage] = {}
            for reference, subcategory in desired.items():
                record = local_by_reference.get(reference)
                if record is None:
                    filename = normalize_media_filename(reference)
                    record = SavedImage.create(
                        note_id=0,
                        card_id=0,
                        deck_name="",
                        note_type="",
                        field_names=[],
                        image_src=reference,
                        media_filename=filename,
                        alt_text="",
                        image_title="",
                        rendered_width=0,
                        rendered_height=0,
                        natural_width=0,
                        natural_height=0,
                        systems=[UNCATEGORIZED_SYSTEM],
                        tags=[],
                        subcategory=subcategory,
                    )
                elif record.subcategory != subcategory:
                    record = replace(record, subcategory=subcategory)
                replacement[record.record_id] = record

            self._records = replacement
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
