import csv
from pathlib import Path

from anking_images.storage import CSV_COLUMNS, SavedImage, SavedImageStore


def make_record(note_id: int = 10, system: str = "Cardiovascular") -> SavedImage:
    return SavedImage.create(
        note_id=note_id,
        card_id=20,
        deck_name="AnKing::Step 1",
        note_type="AnKingOverhaul",
        field_names=["Extra"],
        image_src="heart%20image.jpg",
        media_filename="heart image.jpg",
        alt_text="Heart",
        image_title="Anatomy",
        rendered_width=500,
        rendered_height=400,
        natural_width=1000,
        natural_height=800,
        systems=[system] if system else [],
        tags=[f"#AK_Step1_v12::^Systems::{system}"] if system else [],
    )


def test_creates_csv_with_full_header(tmp_path: Path) -> None:
    path = tmp_path / "user_files" / "saved_images.csv"
    SavedImageStore(path)
    with path.open(newline="", encoding="utf-8") as handle:
        assert tuple(next(csv.reader(handle))) == CSV_COLUMNS


def test_toggle_round_trip_and_remove(tmp_path: Path) -> None:
    path = tmp_path / "saved_images.csv"
    store = SavedImageStore(path)
    record = make_record()

    assert store.toggle(record) is True
    assert store.is_saved(record.note_id, record.media_filename)

    reloaded = SavedImageStore(path)
    assert reloaded.all() == [record]
    assert reloaded.saved_media_for_note(record.note_id) == {"heart image.jpg"}

    assert reloaded.toggle(record) is False
    assert SavedImageStore(path).all() == []


def test_missing_system_becomes_uncategorized(tmp_path: Path) -> None:
    store = SavedImageStore(tmp_path / "saved_images.csv")
    assert store.toggle(make_record(system=""))
    assert store.all()[0].systems == ("Uncategorized",)


def test_delete_removes_record_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "saved_images.csv"
    store = SavedImageStore(path)
    record = make_record()
    store.toggle(record)

    assert store.delete(record.record_id) is True
    assert store.delete(record.record_id) is False
    assert SavedImageStore(path).all() == []


def test_malformed_row_does_not_hide_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "saved_images.csv"
    store = SavedImageStore(path)
    store.toggle(make_record())
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write("broken,row\n")

    reloaded = SavedImageStore(path)
    assert len(reloaded.all()) == 1
