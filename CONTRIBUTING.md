# Contributing

Thank you for your interest. The project is small and unofficial; the most valuable help is **real camera files**.

## 1. Camera test files (most wanted)

The decoding of the file formats is based on pairs of files that differ in exactly one setting. Each new pair maps more settings.

How to make a pair:

1. Save the current state of your camera as a SCENE file and as an ALL file (`before.SCENE`, `before.ALL`).
2. Change **exactly one menu item** (or a small group that belongs together, for example one gamma setting and its level). Do not change anything else. Note that the camera may change other items by itself; that is interesting, too.
3. Save the SCENE and ALL file again (`after.SCENE`, `after.ALL`).
4. Write a short text file (`what-changed.txt`): camera model (FS7 or FS7 II), firmware version, the menu path of the changed item, old and new value, and anything that surprised you.
5. Put all files into a ZIP archive and attach it to a [test report](../../issues/new/choose). (GitHub does not accept `.SCENE` and `.ALL` files directly, a ZIP is fine.)

Before you send files:

- **Remove personal text.** ALL files contain text values such as the clip name (title prefix) and the camera ID. The editor shows them; change them to something neutral in the editor (clip name field) and save with it, not in a text editor: the editor recalculates the checksum in the first line of the file, and plain ASCII characters are safest.
- **Send only your own settings.** Do not send scene files from paid look packs or other people's files without their permission.
- Files are published with the issue. Do not attach anything you do not want to be public.

### User menu files

The user menu (Edit User Menu on the camera) is saved as a `.USER` file. The FS7 II side is decoded completely (all 77 menu items with their sub-elements); what is still open is the **FS7 (Mk1) side** and the conversion between the two cameras. If you own an FS7 (Mk1) or an FS7 II, these files help most:

1. **Your own user menu file** (FS7 or FS7 II): File > User Menu Item > Save SD Card on the camera (see the camera manual for the card folder). The more menu items you have registered, the better; the file only holds the list of the items and which sub-elements are on, no personal data apart from its File ID (the name you gave it; it is shown in the editor and can be changed there).
2. **A report whether the camera accepts a file made with the editor.** Open a `.USER` file in the editor, change something (for example move an item or switch a sub-element off) or switch the model (FS7 <-> FS7M2), save, load it on the camera (File > User Menu Item > Load SD Card) and tell us what happened: did the camera load it, which items did it show, did anything look different from what the editor showed? A converted file is an especially useful test.
3. **FS7 (Mk1) only:** if a menu item in the Mk1 dialog "Edit Sub Item" has other sub-elements, or a different order, than the same item in the editor, a short note with the item name and the order you see helps.

For a new menu item or sub-element that the editor does not know yet: put exactly **one** menu item into the user menu (slot 1), tick all its sub-elements when the camera asks, save the `.USER` file, and write down the name of the item and the sub-elements in the order of the dialog; for the assignment of the flags, save more files with some sub-elements switched off. Files go into a ZIP attached to a test report like the pairs above.

## 2. Bug reports and ideas

Open an [issue](../../issues/new/choose) for a bug. Please include the version (About dialog), your operating system, whether you use the EXE or run the Python file, and what you did. Screenshots help. For questions, ideas and showing what you use the tool for, the [Discussions](../../discussions) are the better place.

## 3. Translations

The translations were made with AI assistance and are not reviewed by native speakers; corrections are very welcome. Texts are translated through catalogs in `translations/` (`de.json`, `es.json`, `fr.json`, `it.json`, `pt.json` = European, `pt_BR.json` = Brazilian Portuguese, `ru.json`, `id.json`, `zh_CN.json` = simplified and `zh_TW.json` = traditional Chinese). The English texts in the code are the keys. To add a language, copy a catalog to `translations/<code>.json`, set `_name` and translate the values; keep placeholders such as `{n}` or `{model}` unchanged. `python -X utf8 -I tools/i18n_keys.py --missing` lists texts that have no translation yet.

## 4. Code and documents

Please open an issue first so that we can agree on the approach. Notes:

- Identifiers, comments and user-facing source texts are in English.
- The program supports Python 3.10 and newer: do not use f-strings with the same quote character inside the braces.
- Unclear decoding results are marked `likely` or `hypothesis` in the parameter databases; nothing is presented as certain without evidence.
- Changes to the file format knowledge belong into the project notes with the evidence.

## Code of conduct

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Contributions are accepted under the MIT License of this project (see `LICENSE`). By sending a contribution you confirm that it is your own work or that you may share it under this license.
