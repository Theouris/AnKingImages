# AnKing Images

An Anki desktop add-on that adds a save star beneath substantive images shown in
the reviewer, previewer, and card layout preview. An image must be at least 100
px wider and taller than the bottom AnKing icon to receive a star. Saved image
metadata is kept in `user_files/saved_images.csv` and displayed in a
system-grouped gallery. Only the selected image filenames/sources are stored in
a suspended card in a standalone **AnKing Images** deck so the selection can
travel through normal Anki sync.

This add-on only works for the Anking Step Deck

## Use

1. Review or preview a card and click the empty **☆** beneath an image. The
   filled **★** means the image is saved. Click it again to remove the image.
2. Open **AnKing Images → My Images** in Anki's menu bar. The standalone
   **AnKing Images** deck holds the sync card but does not open the gallery.
   When AnkiHub is present, the add-on menu is placed immediately after it.
3. Use the ☆ button on a gallery image to add it to the **Favorites** section at
   the top. Use ⇩ to export it as a PNG, or 🗑️ to remove it from the catalogue.
   Deleting a gallery entry does not delete the original Anki media file.
4. Click **⟳ Sync** in the gallery to combine the image IDs in the local CSV
   and suspended Anki catalogue card, then save the pooled list to both.
5. Click a thumbnail for a resizable large view. Scroll or pinch on a mousepad
   to zoom; the native maximize/restore window control remains available.

System sections are generated from the first child of tags matching
`#AK_Step1_v12::^Systems::*`. Images without a matching system tag appear in
**Uncategorized**. New systems appear automatically as soon as their first
image is saved.

The local CSV records the image ID, favorite state, save time, note/card IDs,
deck, note type, source field, media filename, image text/dimensions, extracted
systems, and the note's tags. Saving, unsaving, favoriting, and deleting images
changes only this CSV; it does not modify Anki collection state. The gallery's
**Sync** button unions the local selection with the add-on's single suspended
catalogue card and writes the same compact list of filenames/sources to both.
The same pooling happens after an Anki collection sync, so an image name found
on either side is preserved. Favorites and rich display metadata remain local.
Anki's special `user_files` directory preserves the local mirror across add-on
updates.
