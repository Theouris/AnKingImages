"""Anki lifecycle wiring for AnKing Images."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aqt import gui_hooks, mw
from aqt.qt import QAction, QMenu, QTimer
from aqt.utils import qconnect

from .catalogue import CatalogueSync, DECK_NAME
from .gallery import GalleryDialog
from .reviewer import augment_card_html, handle_js_message
from .storage import SavedImageStore


ADDON_DIR = Path(__file__).resolve().parent.parent
STORE = SavedImageStore(ADDON_DIR / "user_files" / "saved_images.csv")
CATALOGUE = CatalogueSync(STORE)
_gallery: GalleryDialog | None = None
_registered = False
_catalogue_error = ""


def _clean_menu_text(value: str) -> str:
    return value.replace("&", "").strip()


def _refresh_visible_gallery() -> None:
    if _gallery is not None and _gallery.isVisible():
        _gallery.refresh()


def _sync_catalogue_card() -> str:
    global _catalogue_error
    if mw.col is None:
        return "No Anki collection is open, so the sync card was not updated."
    try:
        CATALOGUE.write(mw.col)
    except Exception as error:
        _catalogue_error = str(error)
        return f"The image catalogue could not be synced to Anki: {error}"
    _catalogue_error = ""
    return ""


def _pull_catalogue_card() -> None:
    global _catalogue_error
    if mw.col is None:
        return
    try:
        CATALOGUE.setup_and_pull(mw.col)
    except Exception as error:
        _catalogue_error = str(error)
    else:
        _catalogue_error = ""
    _refresh_visible_gallery()
    if getattr(mw, "state", None) == "deckBrowser":
        QTimer.singleShot(0, mw.deckBrowser.refresh)


def _show_gallery() -> None:
    global _gallery
    if _gallery is None:
        _gallery = GalleryDialog(STORE, mw, _sync_catalogue_card)
    else:
        _gallery.refresh()
    if _catalogue_error:
        _gallery.show_error(
            "The AnKing Images sync card could not be loaded: " + _catalogue_error
        )
    _gallery.show()
    _gallery.raise_()
    _gallery.activateWindow()


def _install_menu() -> None:
    menu_bar = mw.menuBar()
    if menu_bar.findChild(QMenu, "ankingImagesMenu") is not None:
        return

    menu = QMenu("AnKing Images", mw)
    menu.setObjectName("ankingImagesMenu")
    action = QAction("My Images", menu)
    qconnect(action.triggered, _show_gallery)
    menu.addAction(action)

    actions = menu_bar.actions()
    anchor_index = next(
        (
            index
            for index, existing in enumerate(actions)
            if _clean_menu_text(existing.text()).casefold() == "ankihub"
        ),
        None,
    )
    if anchor_index is not None and anchor_index + 1 < len(actions):
        menu_bar.insertMenu(actions[anchor_index + 1], menu)
    else:
        menu_bar.addMenu(menu)


def _on_card_will_show(html: str, card: Any, context: str) -> str:
    return augment_card_html(html, card, context, STORE)


def _on_js_message(
    handled: tuple[bool, Any], message: str, context: Any
) -> tuple[bool, Any]:
    return handle_js_message(
        handled,
        message,
        context,
        STORE,
        _refresh_visible_gallery,
    )


def _on_state_did_change(new_state: str, _old_state: str) -> None:
    if new_state != "overview" or mw.col is None:
        return
    try:
        selected_id = mw.col.decks.selected()
        selected_name = mw.col.decks.name_if_exists(selected_id)
    except Exception:
        return
    if selected_name == DECK_NAME:
        QTimer.singleShot(0, _show_gallery)


def _on_media_sync_state_changed(running: bool) -> None:
    if not running:
        _refresh_visible_gallery()


def _on_profile_will_close() -> None:
    global _gallery
    if _gallery is not None:
        _gallery.close()
        _gallery.deleteLater()
        _gallery = None


def register() -> None:
    global _registered
    if _registered:
        return
    _registered = True
    gui_hooks.main_window_did_init.append(_install_menu)
    gui_hooks.profile_did_open.append(_pull_catalogue_card)
    gui_hooks.profile_will_close.append(_on_profile_will_close)
    gui_hooks.sync_did_finish.append(_pull_catalogue_card)
    gui_hooks.media_sync_did_start_or_stop.append(_on_media_sync_state_changed)
    gui_hooks.state_did_change.append(_on_state_did_change)
    gui_hooks.card_will_show.append(_on_card_will_show)
    gui_hooks.webview_did_receive_js_message.append(_on_js_message)
