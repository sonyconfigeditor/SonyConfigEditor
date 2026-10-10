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

- **Remove personal text.** ALL files contain text values such as the clip name (title prefix) and the camera ID. The editor shows them; change them to something neutral before saving.
- **Send only your own settings.** Do not send scene files from paid look packs or other people's files without their permission.
- Files are published with the issue. Do not attach anything you do not want to be public.

## 2. Bug reports and ideas

Open an [issue](../../issues/new/choose). Please include the version (About dialog), your operating system, whether you use the EXE or run the Python file, and what you did. Screenshots help.

## 3. Translations

Texts are translated through catalogs in `translations/` (`de.json`, `es.json`, `it.json`). The English texts in the code are the keys. To add a language, copy a catalog to `translations/<code>.json`, set `_name` and translate the values; keep placeholders such as `{n}` or `{model}` unchanged. `python -X utf8 -I tools/i18n_keys.py --missing` lists texts that have no translation yet.

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
