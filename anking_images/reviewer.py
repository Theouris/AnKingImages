"""Reviewer HTML augmentation and JavaScript bridge handling."""

from __future__ import annotations

import json
from typing import Any

from aqt import mw

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
  .anking-images-star {
    appearance: none;
    -webkit-appearance: none;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: #8b919a;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font: 22px/1 sans-serif;
    margin: 3px 0 1px;
    min-height: 26px;
    min-width: 26px;
    padding: 0;
    text-align: center;
  }
  .anking-images-star svg {
    display: block;
    height: 21px;
    pointer-events: none;
    width: 18px;
  }
  .anking-images-star:hover,
  .anking-images-star:focus-visible {
    background: rgba(128, 128, 128, 0.16);
    color: #d69b00;
    outline: none;
  }
  .anking-images-star[data-saved="true"] { color: #f2b705; }
  .anking-images-star[disabled] { cursor: wait; opacity: .65; }
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

  function bookmarkIcon(saved) {{
    const path = '<path d="M5 3.5h10a1 1 0 0 1 1 1v15.8l-6-3.8-6 3.8V4.5a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" fill="' + (saved ? 'currentColor' : 'none') + '"></path>';
    return '<svg viewBox="0 0 20 24" aria-hidden="true" focusable="false">' + path + '</svg>';
  }}

  function setSaved(button, saved) {{
    button.dataset.saved = saved ? "true" : "false";
    button.innerHTML = bookmarkIcon(saved);
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

      const button = document.createElement("button");
      button.type = "button";
      button.className = "anking-images-star";
      button.dataset.mediaFilename = filename;
      setSaved(button, saved.has(filename));
      wrapper.appendChild(button);

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

    }});
  }}

  if (typeof onUpdateHook !== "undefined") onUpdateHook.push(installStars);
  else window.setTimeout(installStars, 0);
}})();
</script>
"""
    return html + STAR_STYLE + script


def handle_js_message(
    handled: tuple[bool, Any],
    message: str,
    _context: Any,
    store: SavedImageStore,
    gallery_refresh: Any = None,
) -> tuple[bool, Any]:
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
        if callable(gallery_refresh):
            gallery_refresh()
        response = {"saved": is_saved, "systems": list(record.systems)}
        return True, response
    except Exception as error:
        return True, {"saved": False, "error": str(error)}
