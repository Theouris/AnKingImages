from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace


def _load_addon(monkeypatch: object) -> tuple[ModuleType, SimpleNamespace]:
    hooks = SimpleNamespace(
        main_window_did_init=[],
        profile_did_open=[],
        profile_will_close=[],
        sync_did_finish=[],
        media_sync_did_start_or_stop=[],
        state_did_change=[],
        card_will_show=[],
        webview_did_receive_js_message=[],
    )
    main_window = SimpleNamespace(
        col=None,
        state="deckBrowser",
        deckBrowser=SimpleNamespace(refresh=lambda: None),
    )

    aqt = ModuleType("aqt")
    aqt.gui_hooks = hooks  # type: ignore[attr-defined]
    aqt.mw = main_window  # type: ignore[attr-defined]
    qt = ModuleType("aqt.qt")
    qt.QAction = object  # type: ignore[attr-defined]
    qt.QMenu = object  # type: ignore[attr-defined]
    qt.QTimer = SimpleNamespace(singleShot=lambda *_args: None)  # type: ignore[attr-defined]
    utils = ModuleType("aqt.utils")
    utils.qconnect = lambda *_args: None  # type: ignore[attr-defined]

    catalogue = ModuleType("anking_images.catalogue")

    class FakeCatalogueSync:
        def __init__(self, _store: object) -> None:
            pass

    catalogue.CatalogueSync = FakeCatalogueSync  # type: ignore[attr-defined]
    gallery = ModuleType("anking_images.gallery")
    gallery.GalleryDialog = object  # type: ignore[attr-defined]
    reviewer = ModuleType("anking_images.reviewer")
    reviewer.augment_card_html = lambda *args: args[0]  # type: ignore[attr-defined]
    reviewer.handle_js_message = lambda *args: args[0]  # type: ignore[attr-defined]
    storage = ModuleType("anking_images.storage")
    storage.SavedImageStore = lambda _path: object()  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "aqt", aqt)
    monkeypatch.setitem(sys.modules, "aqt.qt", qt)
    monkeypatch.setitem(sys.modules, "aqt.utils", utils)
    monkeypatch.setitem(sys.modules, "anking_images.catalogue", catalogue)
    monkeypatch.setitem(sys.modules, "anking_images.gallery", gallery)
    monkeypatch.setitem(sys.modules, "anking_images.reviewer", reviewer)
    monkeypatch.setitem(sys.modules, "anking_images.storage", storage)
    monkeypatch.delitem(sys.modules, "anking_images.addon", raising=False)
    return importlib.import_module("anking_images.addon"), hooks


def test_deferred_deck_refresh_stops_after_collection_closes(monkeypatch) -> None:
    addon, _hooks = _load_addon(monkeypatch)
    refreshes: list[bool] = []
    addon.mw.deckBrowser.refresh = lambda: refreshes.append(True)

    addon.mw.col = None
    addon._refresh_deck_browser_if_open()

    assert refreshes == []


def test_register_does_not_open_gallery_on_deck_selection(monkeypatch) -> None:
    addon, hooks = _load_addon(monkeypatch)

    addon.register()

    assert hooks.state_did_change == []
