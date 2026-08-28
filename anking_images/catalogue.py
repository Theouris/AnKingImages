"""Anki-note-backed catalogue synchronization.

The CSV remains the gallery's fast local data source. A single suspended Anki
card carries the same records so normal collection sync can move the catalogue
between devices.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from .storage import CSV_COLUMNS, SavedImage, SavedImageStore


DECK_NAME = "AnKing Images"
NOTETYPE_NAME = "AnKing Images Sync"
CATALOGUE_FIELD = "AnKingImagesCatalogue"
SYNC_GUID = "AKImgsCat1"
SCHEMA_VERSION = 1

_CARD_FRONT = (
    f"{{{{#{CATALOGUE_FIELD}}}}}"
    '<div style="font-family: sans-serif; text-align: center;">'
    "AnKing Images catalogue sync card"
    "</div>"
    f"{{{{/{CATALOGUE_FIELD}}}}}"
)
_CARD_BACK = _CARD_FRONT
_CARD_CSS = ".card { background: #081a2b; color: #eef5ff; }"


def encode_catalogue(
    records: Iterable[SavedImage], *, updated_at_utc: str | None = None
) -> str:
    """Serialize records for the hidden sync note field."""

    updated = updated_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "updated_at_utc": updated,
        "records": [
            record.to_row()
            for record in sorted(records, key=lambda item: item.record_id)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_catalogue(value: str) -> list[SavedImage]:
    """Deserialize and validate a sync note catalogue."""

    try:
        payload = json.loads(str(value or ""))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "The AnKing Images sync catalogue is not valid JSON."
        ) from error
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("The AnKing Images sync catalogue has an unsupported format.")
    rows = payload.get("records")
    if not isinstance(rows, list):
        raise ValueError("The AnKing Images sync catalogue has no records list.")

    records: dict[str, SavedImage] = {}
    for index, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, dict):
            raise ValueError(f"Catalogue record {index} is not an object.")
        row = {
            column: "" if raw_row.get(column) is None else str(raw_row.get(column, ""))
            for column in CSV_COLUMNS
        }
        record = SavedImage.from_row(row)
        if not record.note_id or not (record.media_filename or record.image_src):
            raise ValueError(f"Catalogue record {index} does not identify an image.")
        records[record.record_id] = record
    return list(records.values())


class CatalogueSync:
    """Maintain the standalone deck, suspended card, and CSV mirror."""

    def __init__(self, store: SavedImageStore) -> None:
        self.store = store

    def setup_and_pull(self, collection: Any) -> int:
        """Ensure the sync card exists, then make its catalogue the local CSV."""

        note, _deck_id, created = self._ensure_note(collection)
        if not created:
            try:
                records = decode_catalogue(note[CATALOGUE_FIELD])
            except ValueError:
                self._write_note(collection, note, encode_catalogue(self.store.all()))
            else:
                self.store.replace_all(records)
        return int(note.id)

    def write(self, collection: Any) -> int:
        """Write the current CSV records into the suspended sync card."""

        note, _deck_id, created = self._ensure_note(collection)
        if not created:
            self._write_note(collection, note, encode_catalogue(self.store.all()))
        return int(note.id)

    def _ensure_notetype(self, collection: Any) -> dict[str, Any]:
        models = collection.models
        notetype = models.by_name(NOTETYPE_NAME)
        if notetype is None:
            notetype = models.new(NOTETYPE_NAME)
            models.add_field(notetype, models.new_field(CATALOGUE_FIELD))
            template = models.new_template("Catalogue")
            template["qfmt"] = _CARD_FRONT
            template["afmt"] = _CARD_BACK
            models.add_template(notetype, template)
            notetype["css"] = _CARD_CSS
            models.add(notetype)
            return notetype

        field_names = {str(field.get("name", "")) for field in notetype["flds"]}
        if CATALOGUE_FIELD not in field_names:
            raise RuntimeError(
                f'A note type named "{NOTETYPE_NAME}" already exists but was not '
                "created by AnKing Images. Rename it and restart Anki."
            )

        changed = False
        if not notetype.get("tmpls"):
            template = models.new_template("Catalogue")
            models.add_template(notetype, template)
            changed = True
        template = notetype["tmpls"][0]
        for key, value in (("qfmt", _CARD_FRONT), ("afmt", _CARD_BACK)):
            if template.get(key) != value:
                template[key] = value
                changed = True
        if notetype.get("css") != _CARD_CSS:
            notetype["css"] = _CARD_CSS
            changed = True
        if changed:
            models.update_dict(notetype)
            refreshed = models.by_name(NOTETYPE_NAME)
            if refreshed is not None:
                notetype = refreshed
        return notetype

    def _ensure_note(self, collection: Any) -> tuple[Any, int, bool]:
        deck_id = collection.decks.id(DECK_NAME)
        if deck_id is None:
            raise RuntimeError("Anki could not create the AnKing Images deck.")
        notetype = self._ensure_notetype(collection)
        notes = [
            collection.get_note(note_id)
            for note_id in collection.models.nids(notetype["id"])
        ]

        created = not notes
        if created:
            note = collection.new_note(notetype)
            note.guid = SYNC_GUID
            note[CATALOGUE_FIELD] = encode_catalogue(self.store.all())
            collection.add_note(note, deck_id)
        else:
            matching = [note for note in notes if note.guid == SYNC_GUID]
            candidates = matching or notes
            note = max(
                candidates,
                key=lambda item: (int(getattr(item, "mod", 0)), int(item.id)),
            )
            duplicate_ids = [other.id for other in notes if other.id != note.id]
            if duplicate_ids:
                collection.remove_notes(duplicate_ids)
            if note.guid != SYNC_GUID:
                note.guid = SYNC_GUID
                self._write_note(collection, note, note[CATALOGUE_FIELD])

        cards = list(note.cards())
        if not cards:
            collection.after_note_updates(
                [note.id], mark_modified=True, generate_cards=True
            )
            cards = list(note.cards())
        if not cards:
            raise RuntimeError("Anki could not create the catalogue sync card.")

        card_ids = [card.id for card in cards]
        if any(int(card.did) != int(deck_id) for card in cards):
            collection.set_deck(card_ids, deck_id)
        if any(int(card.queue) != -1 for card in cards):
            collection.sched.suspend_cards(card_ids)
        return note, int(deck_id), created

    @staticmethod
    def _write_note(collection: Any, note: Any, value: str) -> None:
        note[CATALOGUE_FIELD] = value
        try:
            collection.update_note(note, skip_undo_entry=True)
        except TypeError:
            # Anki versions before skip_undo_entry was added still support the
            # same update operation without the optional argument.
            collection.update_note(note)
