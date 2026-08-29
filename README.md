# AnKing Images

An Anki desktop add-on that adds a save bookmark beneath substantive images shown in
the reviewer, previewer, and card layout preview. An image must be at least 100
px wider and taller than the bottom AnKing icon to receive a bookmark. Saved image
metadata is kept in `user_files/saved_images.csv` and displayed in a
subheading-grouped gallery. The selected image IDs and their subheadings are
stored in a suspended card in a standalone **~AnKing Images** deck so the
selection and organization can travel through normal Anki sync.

This add-on only works for the Anking Step Deck

## Use

1. Review or preview a card and click the outlined bookmark beneath an image.
   The filled bookmark means the image is saved. Click it again to remove it.
2. Open **AnKing Images → My Images** in Anki's menu bar. The standalone
   **~AnKing Images** deck holds the sync card but does not open the gallery.
   Moving or renaming that deck does not recreate it. When AnkiHub is present,
   the add-on menu is placed immediately after it.
3. Use the ☆ button on a gallery image to add it to the **Favorites** section at
   the top. Use ↪ to choose an existing subheading or type a new one; leave the
   name blank to move the image to **Uncategorized**. Use ⇩ to export it as a
   PNG, or 🗑️ to remove it from the catalogue. Deleting a gallery entry does not
   delete the original Anki media file.
4. Click **⟳ Sync** in the gallery to combine the image IDs in the local CSV
   and suspended Anki catalogue card, then save the pooled list to both.
5. Click a thumbnail for a resizable large view. Scroll or pinch on a mousepad
   to zoom; the native maximize/restore window control remains available.

An image's initial subheading is generated from the first child of a tag
matching `#AK_Step1_v12::^Systems::*`. Images without a matching system tag
appear in **Uncategorized**. Users can then move an image to any existing or
newly typed subheading.

The local CSV records the image ID, subcategory, favorite state, save time,
note/card IDs, deck, note type, source field, media filename, image
text/dimensions, extracted systems, and the note's tags. Saving, unsaving,
favoriting, moving, and deleting images changes only this CSV; it does not
modify Anki collection state. The gallery's **Sync** button unions the local
selection with the add-on's single suspended catalogue card and writes image
ID/subcategory pairs to both. The same pooling happens after an Anki collection
sync, so an image found on either side is preserved. When the same image exists
on both sides, its CSV subcategory wins. Favorites and rich display metadata
remain local. Anki's special `user_files` directory preserves the local mirror
across add-on updates.
