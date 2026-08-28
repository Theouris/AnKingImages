# AnKing Images

An Anki desktop add-on that adds a save star beneath substantive images shown in
the reviewer, previewer, and card layout preview. An image must be at least 100
px wider and taller than the bottom AnKing icon to receive a star. Saved image
metadata is kept in `user_files/saved_images.csv` and displayed in a
system-grouped gallery. The same catalogue is stored in a suspended card in a
standalone **AnKing Images** deck so it can travel through normal Anki sync.

## Install

Use the prebuilt `AnKingImages.ankiaddon` file, or copy/symlink this directory
into Anki's `addons21` directory. Restart Anki after installing.

## Use

1. Review or preview a card and click the empty **☆** beneath an image. The
   filled **★** means the image is saved. Click it again to remove the image.
2. Click the standalone **AnKing Images** deck to open the gallery, or open
   **AnKing Images → My Images** in Anki's menu bar. When AnkiHub is present,
   the add-on menu is placed immediately after it.
3. Use the ☆ button on a gallery image to add it to the **Favorites** section at
   the top. Use the regular 🗑️ button to remove it from the catalogue. Deleting a
   gallery entry does not delete the original Anki media file.
4. Click a thumbnail for a resizable large view. Scroll or pinch on a mousepad
   to zoom; the native maximize/restore window control remains available.

System sections are generated from the first child of tags matching
`#AK_Step1_v12::^Systems::*`. Images without a matching system tag appear in
**Uncategorized**. New systems appear automatically as soon as their first
image is saved.

The CSV records the image ID, favorite state, save time, note/card IDs, deck,
note type, source field, media filename, image text/dimensions, extracted
systems, and the note's tags. Every save, delete, or favorite change rewrites
the add-on's single suspended catalogue card. After collection sync, that card
rewrites the local CSV, including removals made on another device. Anki's
special `user_files` directory preserves the local mirror across add-on updates.
