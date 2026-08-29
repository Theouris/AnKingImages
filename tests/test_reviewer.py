from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from anking_images.storage import SavedImageStore


class FakeNote:
    id = 10
    tags = ["#AK_Step1_v12::^Systems::Cardiovascular"]

    @staticmethod
    def note_type() -> dict[str, str]:
        return {"name": "AnKingOverhaul"}

    @staticmethod
    def items() -> list[tuple[str, str]]:
        return [("Extra", '<img src="heart.jpg">')]

    def __contains__(self, _field_name: object) -> bool:
        return False


class FakeCard:
    id = 20
    did = 30

    @staticmethod
    def note() -> FakeNote:
        return FakeNote()


class FakeDecks:
    @staticmethod
    def get(deck_id: int) -> dict[str, str]:
        assert deck_id == 30
        return {"name": "AnKing::Step 1"}


class ReadOnlyCollection:
    def __init__(self) -> None:
        self.decks = FakeDecks()
        self.mutation_calls: list[str] = []

    @staticmethod
    def get_card(card_id: int) -> FakeCard:
        assert card_id == 20
        return FakeCard()

    def update_note(self, *_args: object, **_kwargs: object) -> None:
        self.mutation_calls.append("update_note")

    def add_note(self, *_args: object, **_kwargs: object) -> None:
        self.mutation_calls.append("add_note")

    def merge_undo_entries(self, *_args: object, **_kwargs: object) -> None:
        self.mutation_calls.append("merge_undo_entries")


def test_reviewer_star_only_changes_csv(tmp_path: Path, monkeypatch: object) -> None:
    fake_aqt = ModuleType("aqt")
    fake_aqt.mw = SimpleNamespace(col=None)
    monkeypatch.setitem(sys.modules, "aqt", fake_aqt)  # type: ignore[attr-defined]
    reviewer = importlib.import_module("anking_images.reviewer")

    collection = ReadOnlyCollection()
    reviewer.mw.col = collection
    store = SavedImageStore(tmp_path / "saved_images.csv")
    refreshes: list[bool] = []
    payload = {
        "noteId": 10,
        "cardId": 20,
        "imageSrc": "heart.jpg",
        "mediaFilename": "heart.jpg",
        "fieldNames": ["Extra"],
        "renderedWidth": 500,
        "renderedHeight": 400,
        "naturalWidth": 1000,
        "naturalHeight": 800,
        "referenceIconWidth": 40,
        "referenceIconHeight": 40,
    }

    handled, response = reviewer.handle_js_message(
        (False, None),
        reviewer.MESSAGE_PREFIX + json.dumps(payload),
        None,
        store,
        lambda: refreshes.append(True),
    )

    assert handled is True
    assert response["saved"] is True
    assert [record.media_filename for record in store.all()] == ["heart.jpg"]
    assert refreshes == [True]
    assert collection.mutation_calls == []


def test_reviewer_uses_outline_and_filled_bookmark_markup(
    tmp_path: Path, monkeypatch: object
) -> None:
    fake_aqt = ModuleType("aqt")
    fake_aqt.mw = SimpleNamespace(col=None)
    monkeypatch.setitem(sys.modules, "aqt", fake_aqt)  # type: ignore[attr-defined]
    reviewer = importlib.import_module("anking_images.reviewer")

    html = reviewer.augment_card_html(
        '<img src="heart.jpg">',
        FakeCard(),
        "reviewQuestion",
        SavedImageStore(tmp_path / "saved_images.csv"),
    )

    assert "function bookmarkIcon(saved)" in html
    assert "button.innerHTML = bookmarkIcon(saved)" in html
    assert "saved ? 'currentColor' : 'none'" in html
    assert "display: inline-flex" in html
    assert "align-items: center" in html
    assert "justify-content: center" in html
