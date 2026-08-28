"""Qt stylesheet derived from the supplied AnKing Images web CSS."""

GALLERY_STYLESHEET = """
QDialog#ankingImagesGallery,
QDialog#ankingImagesDetail {
    background: #081a2b;
    color: #eef5ff;
    font-family: "Segoe UI", Roboto, Arial, sans-serif;
}
QDialog#ankingImagesGallery QWidget,
QDialog#ankingImagesDetail QWidget {
    color: #eef5ff;
}
QLabel#ankingImagesHeading {
    color: #eef5ff;
    font-size: 24px;
    font-weight: 700;
    padding: 4px 5px 0;
}
QLabel#ankingImagesDetailTitle {
    color: #eef5ff;
    font-size: 16px;
    font-weight: 650;
}
QLabel#ankingImagesMuted,
QLabel#ankingImagesDetails,
QLabel#ankingImagesEmpty {
    color: rgba(238, 245, 255, 184);
}
QLabel#ankingImagesError {
    background: #7a3e00;
    border: 1px solid #b86515;
    border-radius: 8px;
    color: #ffffff;
    padding: 8px;
}
QScrollArea#ankingImagesGalleryScroll,
QScrollArea#ankingImagesDetailScroll {
    background: #081a2b;
    border: 0;
}
QScrollArea#ankingImagesGalleryScroll > QWidget > QWidget,
QScrollArea#ankingImagesDetailScroll > QWidget > QWidget {
    background: #081a2b;
}
QFrame#ankingImagesCard {
    background: #0b2238;
    border: 1px solid rgba(238, 245, 255, 36);
    border-radius: 12px;
    padding: 7px;
}
QLabel#ankingImagesThumbnailMissing {
    background: #0e2b46;
    border: 1px solid rgba(238, 245, 255, 22);
    border-radius: 8px;
    color: rgba(238, 245, 255, 150);
}
QLabel#ankingImagesFilename {
    color: #eef5ff;
    font-size: 12px;
    padding-top: 4px;
}
QToolButton#ankingImagesSection {
    background: rgba(11, 34, 56, 220);
    border: 1px solid rgba(238, 245, 255, 36);
    border-radius: 10px;
    color: #eef5ff;
    font-size: 15px;
    font-weight: 650;
    padding: 11px 13px;
    text-align: left;
}
QToolButton#ankingImagesSection:hover {
    background: #0e2b46;
    border-color: rgba(238, 245, 255, 58);
}
QPushButton#ankingImagesFavorite,
QPushButton#ankingImagesDelete {
    background: #0e2b46;
    border: 1px solid rgba(238, 245, 255, 42);
    border-radius: 8px;
    color: #eef5ff;
    font-size: 18px;
    padding: 1px;
}
QPushButton#ankingImagesFavorite:hover,
QPushButton#ankingImagesDelete:hover {
    background: #153b5d;
    border-color: #6aa6ff;
}
QPushButton#ankingImagesFavorite:pressed,
QPushButton#ankingImagesDelete:pressed {
    background: #081a2b;
}
QPushButton#ankingImagesFavorite[isFavorite="true"] {
    color: #f2b705;
}
QScrollBar:vertical {
    background: rgba(11, 34, 56, 100);
    border: 0;
    margin: 0;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: rgba(238, 245, 255, 90);
    border-radius: 5px;
    min-height: 28px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: 0;
    height: 0;
}
QScrollBar:horizontal {
    background: rgba(11, 34, 56, 100);
    border: 0;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: rgba(238, 245, 255, 90);
    border-radius: 5px;
    min-width: 28px;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    border: 0;
    width: 0;
}
"""
