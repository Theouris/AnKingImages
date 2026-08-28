# AnKing Images

An Anki desktop add-on that adds a save star beneath substantive images shown in
the reviewer, previewer, and card layout preview. An image must be at least 100
px wider and taller than the bottom AnKing icon to receive a star. Saved image
metadata is kept in `user_files/saved_images.csv` and displayed in a
system-grouped gallery.

## Install

Use the prebuilt `AnKingImages.ankiaddon` file, or copy/symlink this directory
into Anki's `addons21` directory. Restart Anki after installing.

## Use

1. Review or preview a card and click the empty **☆** beneath an image. The
   filled **★** means the image is saved. Click it again to remove the image.
2. Open **AnKing Images → My Images** in Anki's menu bar. When AnkiHub is
   present, the add-on menu is placed immediately after it.
3. Open a collapsed system section to load its image thumbnails. Click a
   thumbnail for a resizable large view with fit, zoom, and full-screen controls,
   or use the red trash can to remove it from the gallery. Deleting a gallery
   entry does not delete the original Anki media file.

System sections are generated from the first child of tags matching
`#AK_Step1_v12::^Systems::*`. Images without a matching system tag appear in
**Uncategorized**. New systems appear automatically as soon as their first
image is saved.

The CSV records the save time, note/card IDs, deck, note type, source field,
media filename, image text/dimensions, extracted systems, and the note's tags.
Anki's special `user_files` directory preserves this data across add-on updates.
