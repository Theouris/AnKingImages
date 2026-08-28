from __future__ import annotations

import json
from pathlib import Path

from anking_images.catalogue import (
    CATALOGUE_FIELD,
    DECK_NAME,
    SYNC_GUID,
    CatalogueSync,
    decode_catalogue,
    encode_catalogue,
)
from anking_images.storage import SavedImage, SavedImageStore


def make_record(note_id: int = 10, filename: str = "heart.jpg") -> SavedImage:
    return SavedImage.create(
        note_id=note_id,
        card_id=20,
        deck_name="AnKing::Step 1",
        note_type="AnKingOverhaul",
        field_names=["Extra"],
        image_src=filename,
        media_filename=filename,
        alt_text="Heart",
        image_title="Anatomy",
        rendered_width=500,
        rendered_height=400,
        natural_width=1000,
        natural_height=800,
        systems=["Cardiovascular"],
        tags=["#AK_Step1_v12::^Systems::Cardiovascular"],
    )


class FakeCard:
    def __init__(self, card_id: int, note_id: int, deck_id: int) -> None:
        self.id = card_id
        self.nid = note_id
        self.did = deck_id
        self.queue = 0


class FakeNote:
    def __init__(self, collection: "FakeCollection", notetype: dict) -> None:
        self.collection = collection
        self.id = 0
        self.mid = notetype["id"]
        self.guid = "random"
        self.mod = 0
        self.flushed = False
        self.fields = {field["name"]: "" for field in notetype["flds"]}

    def __getitem__(self, name: str) -> str:
        return self.fields[name]

    def __setitem__(self, name: str, value: str) -> None:
        self.fields[name] = value

    def cards(self) -> list[FakeCard]:
        return [card for card in self.collection.cards if card.nid == self.id]

    def flush(self) -> None:
        self.flushed = True


class FakeModels:
    def __init__(self, collection: "FakeCollection") -> None:
        self.collection = collection
        self.notetypes: dict[str, dict] = {}

    def by_name(self, name: str) -> dict | None:
        return self.notetypes.get(name)

    def new(self, name: str) -> dict:
        return {"id": 0, "name": name, "flds": [], "tmpls": [], "css": ""}

    def new_field(self, name: str) -> dict:
        return {"name": name}

    def add_field(self, notetype: dict, field: dict) -> None:
        notetype["flds"].append(field)

    def new_template(self, name: str) -> dict:
        return {"name": name, "qfmt": "", "afmt": ""}

    def add_template(self, notetype: dict, template: dict) -> None:
        notetype["tmpls"].append(template)

    def add(self, notetype: dict) -> None:
        notetype["id"] = 7
        self.notetypes[notetype["name"]] = notetype

    def update_dict(self, notetype: dict) -> None:
        self.notetypes[notetype["name"]] = notetype

    def nids(self, notetype_id: int) -> list[int]:
        return [
            note_id
            for note_id, note in self.collection.notes.items()
            if note.mid == notetype_id
        ]


class FakeDecks:
    def __init__(self) -> None:
        self.created_names: list[str] = []

    def id(self, name: str) -> int:
        self.created_names.append(name)
        return 55


class FakeScheduler:
    def __init__(self, collection: "FakeCollection") -> None:
        self.collection = collection

    def suspend_cards(self, card_ids: list[int]) -> None:
        for card in self.collection.cards:
            if card.id in card_ids:
                card.queue = -1


class FakeCollection:
    def __init__(self) -> None:
        self.notes: dict[int, FakeNote] = {}
        self.cards: list[FakeCard] = []
        self.models = FakeModels(self)
        self.decks = FakeDecks()
        self.sched = FakeScheduler(self)

    def new_note(self, notetype: dict) -> FakeNote:
        return FakeNote(self, notetype)

    def add_note(self, note: FakeNote, deck_id: int) -> None:
        note.id = 100
        note.mod = 1
        self.notes[note.id] = note
        self.cards.append(FakeCard(200, note.id, deck_id))

    def get_note(self, note_id: int) -> FakeNote:
        return self.notes[note_id]

    def update_note(self, note: FakeNote, skip_undo_entry: bool = False) -> None:
        note.mod += 1

    def remove_notes(self, note_ids: list[int]) -> None:
        for note_id in note_ids:
            self.notes.pop(note_id, None)
        self.cards = [card for card in self.cards if card.nid not in note_ids]

    def after_note_updates(
        self, note_ids: list[int], mark_modified: bool, generate_cards: bool = True
    ) -> None:
        for note_id in note_ids:
            if not any(card.nid == note_id for card in self.cards):
                self.cards.append(FakeCard(200, note_id, 1))

    def set_deck(self, card_ids: list[int], deck_id: int) -> None:
        for card in self.cards:
            if card.id in card_ids:
                card.did = deck_id


def test_catalogue_contains_only_deduplicated_image_references() -> None:
    record = make_record()
    favorite = SavedImage.from_row({**record.to_row(), "favorite": "1"})

    encoded = encode_catalogue([record, favorite])

    assert encoded == '["heart.jpg"]'
    assert decode_catalogue(encoded) == ["heart.jpg"]


def test_old_metadata_catalogue_is_read_as_compact_references() -> None:
    old_payload = {
        "schema_version": 1,
        "updated_at_utc": "2026-08-28T00:00:00+00:00",
        "records": [make_record().to_row()],
    }

    assert decode_catalogue(json.dumps(old_payload)) == ["heart.jpg"]


def test_setup_creates_standalone_suspended_sync_card(tmp_path: Path) -> None:
    store = SavedImageStore(tmp_path / "saved_images.csv")
    store.toggle(make_record())
    collection = FakeCollection()

    CatalogueSync(store).setup_and_pull(collection)

    note = collection.notes[100]
    assert collection.decks.created_names == [DECK_NAME]
    assert note.guid == SYNC_GUID
    assert decode_catalogue(note[CATALOGUE_FIELD]) == ["heart.jpg"]
    assert [(card.did, card.queue) for card in collection.cards] == [(55, -1)]


def test_synced_card_replaces_csv_and_propagates_deletions(tmp_path: Path) -> None:
    store = SavedImageStore(tmp_path / "saved_images.csv")
    first = make_record(10)
    second = make_record(11, "brain.jpg")
    store.replace_all([first, second])
    collection = FakeCollection()
    sync = CatalogueSync(store)
    sync.setup_and_pull(collection)

    collection.notes[100][CATALOGUE_FIELD] = encode_catalogue(
        [second], updated_at_utc="2026-08-28T00:00:00+00:00"
    )
    sync.setup_and_pull(collection)

    assert store.all() == [second]


def test_old_metadata_card_is_rewritten_in_compact_format(tmp_path: Path) -> None:
    store = SavedImageStore(tmp_path / "saved_images.csv")
    record = make_record()
    collection = FakeCollection()
    sync = CatalogueSync(store)
    sync.setup_and_pull(collection)
    note = collection.notes[100]
    note[CATALOGUE_FIELD] = json.dumps(
        {"schema_version": 1, "records": [record.to_row()]}
    )

    sync.setup_and_pull(collection)

    assert note[CATALOGUE_FIELD] == '["heart.jpg"]'


def test_local_change_rewrites_existing_sync_note_with_references_only(
    tmp_path: Path,
) -> None:
    store = SavedImageStore(tmp_path / "saved_images.csv")
    record = make_record()
    store.toggle(record)
    collection = FakeCollection()
    sync = CatalogueSync(store)
    sync.setup_and_pull(collection)

    store.toggle(make_record(11, "brain.jpg"))
    sync.write(collection)

    assert decode_catalogue(collection.notes[100][CATALOGUE_FIELD]) == [
        "brain.jpg",
        "heart.jpg",
    ]


def test_old_anki_write_fallback_does_not_create_an_undo_entry(
    tmp_path: Path,
) -> None:
    store = SavedImageStore(tmp_path / "saved_images.csv")
    collection = FakeCollection()
    sync = CatalogueSync(store)
    sync.setup_and_pull(collection)
    note = collection.notes[100]

    def old_update_note(updated_note: FakeNote) -> None:
        updated_note.mod += 1

    collection.update_note = old_update_note  # type: ignore[method-assign]
    store.toggle(make_record())
    sync.write(collection)

    assert note.flushed is True
