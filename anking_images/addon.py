"""Anki lifecycle wiring for AnKing Images."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aqt import gui_hooks, mw
from aqt.qt import QAction, QMenu
from aqt.utils import qconnect

from .gallery import GalleryDialog
from .reviewer import augment_card_html, handle_js_message
from .storage import SavedImageStore


ADDON_DIR = Path(__file__).resolve().parent.parent
STORE = SavedImageStore(ADDON_DIR / "user_files" / "saved_images.csv")
_gallery: GalleryDialog | None = None
_registered = False


def _clean_menu_text(value: str) -> str:
    return value.replace("&", "").strip()


def _refresh_visible_gallery() -> None:
    if _gallery is not None and _gallery.isVisible():
        _gallery.refresh()


def _show_gallery() -> None:
    global _gallery
    if _gallery is None:
        _gallery = GalleryDialog(STORE, mw)
    else:
        _gallery.refresh()
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
    return handle_js_message(handled, message, context, STORE, _refresh_visible_gallery)


def register() -> None:
    global _registered
    if _registered:
        return
    _registered = True
    gui_hooks.main_window_did_init.append(_install_menu)
    gui_hooks.card_will_show.append(_on_card_will_show)
    gui_hooks.webview_did_receive_js_message.append(_on_js_message)
