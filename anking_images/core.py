"""Pure helpers shared by the Anki integration and tests."""

from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Iterable, Mapping
from urllib.parse import unquote, urlsplit


SYSTEM_TAG_PREFIX = "#AK_Step1_v12::^Systems::"
UNCATEGORIZED_SYSTEM = "Uncategorized"
MINIMUM_ICON_SIZE_MARGIN = 100


def normalize_media_filename(source: str) -> str:
    """Return the media filename represented by an HTML image source."""

    value = html.unescape(str(source or "")).strip()
    if not value or value.lower().startswith("data:"):
        return ""

    try:
        path = urlsplit(value).path
    except ValueError:
        path = value.split("?", 1)[0].split("#", 1)[0]

    path = unquote(path).replace("\\", "/").rstrip("/")
    return PurePosixPath(path).name if path else ""


def record_id_for(note_id: int | str, media_filename: str, image_src: str = "") -> str:
    """Build a stable identifier for an image occurrence on a note."""

    identity = normalize_media_filename(media_filename) or str(image_src).strip()
    raw = f"{int(note_id)}\x1f{identity}".encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(raw).hexdigest()[:24]


def is_large_enough_for_star(
    image_width: object,
    image_height: object,
    icon_width: object,
    icon_height: object,
    margin: object = MINIMUM_ICON_SIZE_MARGIN,
) -> bool:
    """Return whether an image exceeds the reference icon by the required margin."""

    def dimension(value: object) -> float:
        try:
            return max(float(str(value or 0)), 0)
        except (TypeError, ValueError):
            return 0

    image = (dimension(image_width), dimension(image_height))
    icon = (dimension(icon_width), dimension(icon_height))
    required_margin = dimension(margin)
    return bool(
        all(image)
        and image[0] >= icon[0] + required_margin
        and image[1] >= icon[1] + required_margin
    )


def extract_systems(tags: Iterable[str]) -> list[str]:
    """Extract first-level AnKing Step 1 system names from note tags."""

    prefix_folded = SYSTEM_TAG_PREFIX.casefold()
    found: dict[str, str] = {}
    for tag in tags:
        value = str(tag).strip()
        if not value.casefold().startswith(prefix_folded):
            continue
        remainder = value[len(SYSTEM_TAG_PREFIX) :]
        system = remainder.split("::", 1)[0].strip()
        if system:
            found.setdefault(system.casefold(), system)
    return sorted(found.values(), key=str.casefold)


def display_system_name(system: str) -> str:
    """Make an AnKing system tag segment pleasant to read in the UI."""

    if system == UNCATEGORIZED_SYSTEM:
        return system
    return re.sub(r"\s+", " ", system.replace("_", " ")).strip() or system


class _ImageSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "img":
            return
        for name, value in attrs:
            if name.casefold() == "src" and value:
                self.sources.append(value)
                break


def image_sources_from_html(value: str) -> list[str]:
    parser = _ImageSourceParser()
    try:
        parser.feed(value or "")
        parser.close()
    except Exception:
        # HTMLParser is intentionally forgiving, but a broken field should not
        # prevent controls from appearing on the rest of the card.
        return parser.sources
    return parser.sources


def fields_by_media(
    fields: Mapping[str, str] | Iterable[tuple[str, str]],
) -> dict[str, list[str]]:
    """Map each media filename in a note to the fields containing it."""

    items = fields.items() if isinstance(fields, Mapping) else fields
    result: dict[str, list[str]] = {}
    for field_name, field_value in items:
        for source in image_sources_from_html(str(field_value)):
            media_filename = normalize_media_filename(source)
            if not media_filename:
                continue
            names = result.setdefault(media_filename, [])
            if str(field_name) not in names:
                names.append(str(field_name))
    return result
