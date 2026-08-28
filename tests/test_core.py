from anking_images.core import (
    UNCATEGORIZED_SYSTEM,
    display_system_name,
    extract_systems,
    fields_by_media,
    is_large_enough_for_star,
    normalize_media_filename,
    record_id_for,
)


def test_extracts_unique_first_level_systems() -> None:
    tags = [
        "#AK_Step1_v12::^Systems::Cardiovascular::Anatomy",
        "#AK_Step1_v12::^Systems::Cardiovascular::Pathology",
        "#AK_Step1_v12::^Systems::Gastrointestinal",
        "unrelated",
    ]
    assert extract_systems(tags) == ["Cardiovascular", "Gastrointestinal"]


def test_system_prefix_is_matched_case_insensitively() -> None:
    assert extract_systems(["#ak_step1_v12::^systems::Renal"]) == ["Renal"]


def test_normalizes_encoded_and_qualified_media_source() -> None:
    assert (
        normalize_media_filename("http://127.0.0.1:123/media/My%20Image.jpg?v=1")
        == "My Image.jpg"
    )
    assert normalize_media_filename("folder\\image.png") == "image.png"
    assert normalize_media_filename("data:image/png;base64,abc") == ""


def test_maps_image_files_to_note_fields() -> None:
    fields = {
        "Text": '<div><img src="one.jpg"><img src="two%20words.png"></div>',
        "Extra": '<img alt="same" src="one.jpg">',
    }
    assert fields_by_media(fields) == {
        "one.jpg": ["Text", "Extra"],
        "two words.png": ["Text"],
    }


def test_record_id_is_stable_and_note_specific() -> None:
    assert record_id_for(12, "a.jpg") == record_id_for("12", "a.jpg")
    assert record_id_for(12, "a.jpg") != record_id_for(13, "a.jpg")


def test_display_system_name() -> None:
    assert display_system_name("Ear_Nose_Throat") == "Ear Nose Throat"
    assert display_system_name(UNCATEGORIZED_SYSTEM) == UNCATEGORIZED_SYSTEM


def test_star_size_requires_100_pixels_beyond_reference_icon() -> None:
    assert is_large_enough_for_star(140, 150, 40, 50)
    assert not is_large_enough_for_star(139, 150, 40, 50)
    assert not is_large_enough_for_star(140, 149, 40, 50)
    assert not is_large_enough_for_star(0, 0, 40, 50)
