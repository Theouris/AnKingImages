"""Anki-note-backed catalogue synchronization.

The CSV remains the gallery's rich local data source. A single suspended Anki
card carries only the selected image filenames/sources so normal collection
sync can move the selection between devices.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from .storage import SavedImage, SavedImageStore, catalogue_reference


DECK_NAME = "AnKing Images"
NOTETYPE_NAME = "AnKing Images Sync"
CATALOGUE_FIELD = "AnKingImagesCatalogue"
SYNC_GUID = "AKImgsCat1"
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
    """Serialize only image filenames/sources for the hidden sync note field.

    ``updated_at_utc`` remains accepted so callers of the first catalogue format
    do not break, but timestamps and local display metadata are intentionally not
    stored on the Anki note.
    """

    del updated_at_utc
    references = sorted(
        {reference for record in records if (reference := catalogue_reference(record))},
        key=str.casefold,
    )
    return json.dumps(references, ensure_ascii=False, separators=(",", ":"))


def decode_catalogue(value: str) -> list[str]:
    """Deserialize a compact catalogue, including the original v1 format."""

    try:
        payload = json.loads(str(value or ""))
    except (TypeError, ValueError) as error:
        raise ValueError(
            "The AnKing Images sync catalogue is not valid JSON."
        ) from error
    if isinstance(payload, list):
        raw_references = payload
    elif isinstance(payload, dict) and payload.get("schema_version") == 1:
        # Seamlessly migrate cards written by the metadata-heavy first format.
        rows = payload.get("records")
        if not isinstance(rows, list):
            raise ValueError("The AnKing Images sync catalogue has no records list.")
        raw_references = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise ValueError(f"Catalogue record {index} is not an object.")
            raw_references.append(row.get("media_filename") or row.get("image_src"))
    else:
        raise ValueError("The AnKing Images sync catalogue has an unsupported format.")

    references: dict[str, None] = {}
    for index, raw_reference in enumerate(raw_references, start=1):
        reference = str(raw_reference or "").strip()
        if not reference:
            raise ValueError(f"Catalogue record {index} does not identify an image.")
        references[reference] = None
    return list(references)


class CatalogueSync:
    """Maintain the standalone deck and a pooled card/CSV catalogue."""

    def __init__(self, store: SavedImageStore) -> None:
        self.store = store

    def setup_and_pull(self, collection: Any) -> int:
        """Ensure the sync card exists, then pool its names with the local CSV."""

        note, _deck_id, created = self._ensure_note(collection)
        if not created:
            self._pool_catalogues(collection, note)
        return int(note.id)

    def write(self, collection: Any) -> int:
        """Pool CSV/card image names and persist the result to both stores."""

        previous_undo_step = self._previous_undo_step(collection)
        try:
            note, _deck_id, created = self._ensure_note(collection)
            if not created:
                self._pool_catalogues(collection, note)
            return int(note.id)
        finally:
            self._merge_with_previous_undo(collection, previous_undo_step)

    def _pool_catalogues(self, collection: Any, note: Any) -> None:
        """Union image names from the card and CSV, retaining local metadata."""

        local_references = [
            reference
            for record in self.store.all()
            if (reference := catalogue_reference(record))
        ]
        try:
            card_references = decode_catalogue(note[CATALOGUE_FIELD])
        except ValueError:
            # Keep valid local data when upgrading or repairing a malformed card.
            card_references = []

        pooled_references = list(
            dict.fromkeys([*local_references, *card_references])
        )
        self.store.replace_catalogue_references(pooled_references)
        compact_value = encode_catalogue(self.store.all())
        if note[CATALOGUE_FIELD] != compact_value:
            self._write_note(collection, note, compact_value)

    @staticmethod
    def _previous_undo_step(collection: Any) -> int | None:
        """Capture an existing review undo step before catalogue maintenance."""

        try:
            status = collection.undo_status()
            step = int(status.last_step)
        except (AttributeError, TypeError, ValueError):
            return None
        return step if status.undo and step > 0 else None

    @staticmethod
    def _merge_with_previous_undo(collection: Any, step: int | None) -> None:
        """Keep first-time sync-card setup from replacing the review undo."""

        if step is None:
            return
        try:
            collection.merge_undo_entries(step)
        except AttributeError:
            # Older Anki releases do not expose undo merging. Their note-update
            # fallback still avoids adding a separate update operation.
            pass

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
            # A normal update_note() call creates an undo entry on older Anki
            # versions and can displace the user's latest review action.
            note.flush()
