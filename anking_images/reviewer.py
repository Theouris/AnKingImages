"""Reviewer HTML augmentation and JavaScript bridge handling."""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote_to_bytes

from aqt import mw
from aqt.qt import QFileDialog, QPixmap
from aqt.utils import showWarning, tooltip

from .catalogue import CATALOGUE_FIELD
from .core import (
    MINIMUM_ICON_SIZE_MARGIN,
    extract_systems,
    fields_by_media,
    is_large_enough_for_star,
    normalize_media_filename,
)
from .storage import SavedImage, SavedImageStore


MESSAGE_PREFIX = "anking-images:toggle:"
EXPORT_MESSAGE_PREFIX = "anking-images:export-png:"
SUPPORTED_CONTEXTS = {
    "reviewQuestion",
    "reviewAnswer",
    "previewQuestion",
    "previewAnswer",
    "clayoutQuestion",
    "clayoutAnswer",
}


STAR_STYLE = """
<style id="anking-images-star-style">
  .anking-images-wrap {
    display: inline-flex !important;
    flex-direction: column;
    align-items: center;
    max-width: 100%;
    vertical-align: middle;
  }
  .anking-images-wrap > img { max-width: 100%; }
  .anking-images-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    margin: 3px 0 1px;
  }
  .anking-images-action {
    appearance: none;
    -webkit-appearance: none;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: #8b919a;
    cursor: pointer;
    font: 22px/1 sans-serif;
    min-height: 26px;
    min-width: 26px;
    padding: 1px 3px 3px;
    text-align: center;
  }
  .anking-images-action:hover,
  .anking-images-action:focus-visible {
    background: rgba(128, 128, 128, 0.16);
    color: #d69b00;
    outline: none;
  }
  .anking-images-star[data-saved="true"] { color: #f2b705; }
  .anking-images-action[disabled] { cursor: wait; opacity: .65; }
</style>
"""


def _json_for_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def _note_type_name(note: Any) -> str:
    try:
        note_type = note.note_type()
    except AttributeError:
        note_type = note.model()
    return str((note_type or {}).get("name", ""))


def _deck_name(card: Any) -> str:
    if mw.col is None:
        return ""
    try:
        deck = mw.col.decks.get(card.did)
    except Exception:
        return ""
    return str((deck or {}).get("name", ""))


def augment_card_html(
    html: str, card: Any, context: str, store: SavedImageStore
) -> str:
    if context not in SUPPORTED_CONTEXTS:
        return html

    try:
        note = card.note()
        if CATALOGUE_FIELD in note:
            return html
        note_id = int(note.id)
        card_id = int(card.id)
        field_map = fields_by_media(note.items())
        saved_media = sorted(store.saved_media_for_note(note_id))
    except Exception:
        return html

    config = {
        "noteId": note_id,
        "cardId": card_id,
        "fieldsByMedia": field_map,
        "savedMedia": saved_media,
        "messagePrefix": MESSAGE_PREFIX,
        "exportMessagePrefix": EXPORT_MESSAGE_PREFIX,
        "minimumIconSizeMargin": MINIMUM_ICON_SIZE_MARGIN,
    }
    script = f"""
<script>
(() => {{
  const config = {_json_for_script(config)};

  function mediaName(source) {{
    let value = String(source || "").trim();
    if (!value || value.toLowerCase().startsWith("data:")) return "";
    value = value.split("#", 1)[0].split("?", 1)[0].replace(/\\\\/g, "/");
    try {{ value = decodeURIComponent(value); }} catch (_) {{}}
    return value.slice(value.lastIndexOf("/") + 1);
  }}

  function setSaved(button, saved) {{
    button.dataset.saved = saved ? "true" : "false";
    button.textContent = saved ? "★" : "☆";
    button.title = saved ? "Remove from My Images" : "Save to My Images";
    button.setAttribute("aria-label", button.title);
    button.setAttribute("aria-pressed", saved ? "true" : "false");
  }}

  function setAllForMedia(filename, saved) {{
    document.querySelectorAll(".anking-images-star").forEach((button) => {{
      if (button.dataset.mediaFilename === filename) setSaved(button, saved);
    }});
  }}

  function imageDimensions(image) {{
    const box = image.getBoundingClientRect();
    return {{
      width: box.width > 0 ? box.width : (image.naturalWidth || 0),
      height: box.height > 0 ? box.height : (image.naturalHeight || 0)
    }};
  }}

  function imageSignature(image) {{
    return [
      image.getAttribute("src") || "",
      image.getAttribute("alt") || "",
      image.getAttribute("title") || "",
      image.id || "",
      typeof image.className === "string" ? image.className : ""
    ].join(" ").toLowerCase();
  }}

  function bottommost(images) {{
    return images.reduce((lowest, image) => {{
      if (!lowest) return image;
      return image.getBoundingClientRect().bottom >= lowest.getBoundingClientRect().bottom
        ? image : lowest;
    }}, null);
  }}

  function findAnKingIcon(images) {{
    const named = images.filter((image) => imageSignature(image).includes("anking"));
    return bottommost(named.length ? named : images);
  }}

  function waitForImage(image) {{
    if (image.dataset.ankingImagesWaiting === "true") return;
    image.dataset.ankingImagesWaiting = "true";
    image.addEventListener("load", () => {{
      delete image.dataset.ankingImagesWaiting;
      installStars();
    }}, {{ once: true }});
  }}

  function installStars() {{
    const saved = new Set(config.savedMedia);
    const images = Array.from(
      document.querySelectorAll("img:not([data-anking-images-ignore])")
    );
    const ankingIcon = findAnKingIcon(images);
    if (ankingIcon && (!ankingIcon.complete || !ankingIcon.naturalWidth || !ankingIcon.naturalHeight)) {{
      waitForImage(ankingIcon);
      return;
    }}
    const iconDimensions = ankingIcon
      ? imageDimensions(ankingIcon) : {{ width: 0, height: 0 }};

    images.forEach((image) => {{
      if (image.dataset.ankingImagesReady === "true") return;
      if (!image.complete || !image.naturalWidth || !image.naturalHeight) {{
        waitForImage(image);
        return;
      }}
      image.dataset.ankingImagesReady = "true";

      const dimensions = imageDimensions(image);
      const isLargeEnough = image !== ankingIcon
        && dimensions.width >= iconDimensions.width + config.minimumIconSizeMargin
        && dimensions.height >= iconDimensions.height + config.minimumIconSizeMargin;
      if (!isLargeEnough) return;

      const source = image.getAttribute("src") || "";
      const filename = mediaName(source);
      const wrapper = document.createElement("span");
      wrapper.className = "anking-images-wrap";
      image.parentNode.insertBefore(wrapper, image);
      wrapper.appendChild(image);

      const actions = document.createElement("span");
      actions.className = "anking-images-actions";
      wrapper.appendChild(actions);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "anking-images-action anking-images-star";
      button.dataset.mediaFilename = filename;
      setSaved(button, saved.has(filename));
      actions.appendChild(button);

      const exportButton = document.createElement("button");
      exportButton.type = "button";
      exportButton.className = "anking-images-action anking-images-export";
      exportButton.textContent = "⇩";
      exportButton.title = "Save image as PNG";
      exportButton.setAttribute("aria-label", exportButton.title);
      actions.appendChild(exportButton);

      button.addEventListener("click", (event) => {{
        event.preventDefault();
        event.stopPropagation();
        if (button.disabled) return;
        button.blur();

        const desired = button.dataset.saved !== "true";
        setAllForMedia(filename, desired);
        button.disabled = true;
        const box = image.getBoundingClientRect();
        const payload = {{
          noteId: config.noteId,
          cardId: config.cardId,
          imageSrc: source,
          mediaFilename: filename,
          fieldNames: config.fieldsByMedia[filename] || [],
          altText: image.getAttribute("alt") || "",
          imageTitle: image.getAttribute("title") || "",
          renderedWidth: Math.round(box.width),
          renderedHeight: Math.round(box.height),
          naturalWidth: image.naturalWidth || 0,
          naturalHeight: image.naturalHeight || 0,
          referenceIconWidth: Math.round(iconDimensions.width),
          referenceIconHeight: Math.round(iconDimensions.height)
        }};

        try {{
          pycmd(config.messagePrefix + JSON.stringify(payload), (result) => {{
            button.disabled = false;
            if (result && typeof result.saved === "boolean") {{
              setAllForMedia(filename, result.saved);
            }} else {{
              setAllForMedia(filename, !desired);
            }}
          }});
        }} catch (_) {{
          button.disabled = false;
          setAllForMedia(filename, !desired);
        }}
      }});

      exportButton.addEventListener("click", (event) => {{
        event.preventDefault();
        event.stopPropagation();
        if (exportButton.disabled) return;
        exportButton.blur();
        exportButton.disabled = true;
        try {{
          pycmd(config.exportMessagePrefix + JSON.stringify({{
            imageSrc: source,
            mediaFilename: filename
          }}), () => {{
            exportButton.disabled = false;
          }});
        }} catch (_) {{
          exportButton.disabled = false;
        }}
      }});
    }});
  }}

  if (typeof onUpdateHook !== "undefined") onUpdateHook.push(installStars);
  else window.setTimeout(installStars, 0);
}})();
</script>
"""
    return html + STAR_STYLE + script


def _pixmap_for_source(image_src: str, media_filename: str) -> QPixmap:
    if mw.col is not None and media_filename:
        candidate = Path(mw.col.media.dir()) / media_filename
        if candidate.is_file():
            pixmap = QPixmap(str(candidate))
            if not pixmap.isNull():
                return pixmap

    if image_src.lower().startswith("data:image/"):
        try:
            header, data = image_src.split(",", 1)
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


def _export_png(payload: dict[str, Any]) -> dict[str, Any]:
    image_src = str(payload.get("imageSrc", ""))
    media_filename = normalize_media_filename(
        str(payload.get("mediaFilename", "")) or image_src
    )
    pixmap = _pixmap_for_source(image_src, media_filename)
    if pixmap.isNull():
        raise ValueError("The source image could not be loaded.")

    stem = Path(media_filename or "anki-image").stem or "anki-image"
    selected, _chosen_filter = QFileDialog.getSaveFileName(
        mw,
        "Save image as PNG",
        f"{stem}.png",
        "PNG images (*.png)",
    )
    if not selected:
        return {"exported": False, "cancelled": True}
    destination = Path(selected)
    if destination.suffix.casefold() != ".png":
        destination = destination.with_name(destination.name + ".png")
    if not pixmap.save(str(destination), "PNG"):
        raise OSError(f'Could not write "{destination}".')
    tooltip(f'Saved PNG as "{destination.name}".', parent=mw)
    return {"exported": True}


def handle_js_message(
    handled: tuple[bool, Any],
    message: str,
    _context: Any,
    store: SavedImageStore,
    gallery_refresh: Any = None,
    catalogue_changed: Any = None,
) -> tuple[bool, Any]:
    if message.startswith(EXPORT_MESSAGE_PREFIX):
        if mw.col is None:
            return True, {"exported": False, "error": "No collection is open."}
        try:
            payload = json.loads(message[len(EXPORT_MESSAGE_PREFIX) :])
            if not isinstance(payload, dict):
                raise ValueError("The image export request is invalid.")
            return True, _export_png(payload)
        except Exception as error:
            showWarning(f"The image could not be saved as PNG: {error}", parent=mw)
            return True, {"exported": False, "error": str(error)}

    if not message.startswith(MESSAGE_PREFIX):
        return handled
    if mw.col is None:
        return True, {"saved": False, "error": "No collection is open."}

    try:
        payload = json.loads(message[len(MESSAGE_PREFIX) :])
        card_id = int(payload["cardId"])
        note_id = int(payload["noteId"])
        card = mw.col.get_card(card_id)
        note = card.note()
        if int(note.id) != note_id:
            raise ValueError("The displayed card no longer matches the note.")

        image_src = str(payload.get("imageSrc", ""))
        media_filename = normalize_media_filename(
            str(payload.get("mediaFilename", "")) or image_src
        )
        if not media_filename and not image_src:
            raise ValueError("This image has no usable source.")
        if not is_large_enough_for_star(
            payload.get("renderedWidth", 0),
            payload.get("renderedHeight", 0),
            payload.get("referenceIconWidth", 0),
            payload.get("referenceIconHeight", 0),
        ):
            raise ValueError(
                "Images must be at least 100 px wider and taller than the AnKing icon."
            )

        tags = tuple(str(tag) for tag in note.tags)
        systems = tuple(extract_systems(tags))
        actual_fields = fields_by_media(note.items()).get(media_filename, [])
        requested_fields = payload.get("fieldNames", [])
        field_names = actual_fields or (
            [str(name) for name in requested_fields]
            if isinstance(requested_fields, list)
            else []
        )
        record = SavedImage.create(
            note_id=note_id,
            card_id=card_id,
            deck_name=_deck_name(card),
            note_type=_note_type_name(note),
            field_names=field_names,
            image_src=image_src,
            media_filename=media_filename,
            alt_text=str(payload.get("altText", "")),
            image_title=str(payload.get("imageTitle", "")),
            rendered_width=payload.get("renderedWidth", 0),
            rendered_height=payload.get("renderedHeight", 0),
            natural_width=payload.get("naturalWidth", 0),
            natural_height=payload.get("naturalHeight", 0),
            systems=systems,
            tags=tags,
        )
        is_saved = store.toggle(record)
        sync_warning = ""
        if callable(catalogue_changed):
            try:
                result = catalogue_changed()
                if isinstance(result, str):
                    sync_warning = result
            except Exception as error:
                sync_warning = str(error)
        if callable(gallery_refresh):
            gallery_refresh()
        response = {"saved": is_saved, "systems": list(record.systems)}
        if sync_warning:
            response["syncWarning"] = sync_warning
        return True, response
    except Exception as error:
        return True, {"saved": False, "error": str(error)}
