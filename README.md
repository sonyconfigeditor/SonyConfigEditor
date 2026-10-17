# Sony Config Editor

<img src="assets/sonyconfigeditor.png" alt="Sony Config Editor logo" width="120">

A desktop tool to read, edit, convert and write the configuration files of the Sony **PXW-FS7** and **PXW-FS7M2** cinema cameras: **SCENE files** (`.SCENE`) and **ALL files** (`.ALL`, the complete camera settings).

> **Unofficial project.** Not affiliated with, supported by or endorsed by Sony. Sony, PXW-FS7 and PXW-FS7M2 are trademarks of their respective owners. The file formats were researched by comparing real camera files. **Use at your own risk:** back up your camera first (save an All File to the SD card) and test new files on the camera before relying on them. Not every decoded setting is confirmed - see "Status of the decoding".

## What it is for

- Edit a scene look (gamma, matrix, detail, black, white clip, ...) on the computer with the camera's own menu names and value ranges instead of raw numbers.
- **Use SCENE files from the FS7 on the FS7M2 and back** (e.g. looks bought or downloaded for the Mk1). The conversion keeps camera-specific values on the target model's state and restores the lost values when you switch back.
- Combine and review: compare settings, import single values from other files, build a new file from neutral defaults.

## Features

- Opens `.SCENE` and `.ALL` files (menu, recent files list, command line or drag and drop); the checksum is verified and rewritten on save, files round-trip byte-identically.
- Settings are grouped like the camera's menus (one tab per main menu: System, Camera, Paint, Audio, VF, TC/UB, Recording, File, with the camera's sub-menus inside) with dropdowns, step fields (+/- buttons) and check boxes. Unknown IDs stay visible as raw values and are written back unchanged.
- **Options that are impossible in the current state are greyed out** (e.g. RAW 4096 needs Imager Scan Mode Normal, Detail settings with Detail Off, BT.2020 only on the FS7M2 with a 4K format) and implausible combinations raise a warning.
- **Type switch SCENE / ALL** and **model switch FS7 / FS7M2** in the header: only mapped values are carried over, everything else stays stored and returns when you switch back.
- **Expand all / Collapse all** (View menu, Ctrl+Shift+Down / Up, or the buttons next to the filter) for the sub-groups of the shown tab.
- **Appearance** (View menu): System, Day or Night mode, remembered between runs.
- **Tabs** for the camera's main menus (System, Camera, Paint, Audio, VF, TC/UB, Recording, File, Unknown) across the top show one menu at a time, with the number of parameters; each tab remembers where you were. Rows that do not apply (e.g. the ISO rows while the gain mode is dB) are greyed out and sorted below the usable ones.
- **VF tab with a virtual camera monitor** (ALL files): the picture of the camera monitor shows the display elements at their places with example values, and every check box is connected to the file (VF > Display On/Off, plus Center Marker): switching one changes the file, editing the file in the table changes the picture. The markers of VF > Marker (safety zone, aspect marker or mask, user box, 100 % marker, center marker) are drawn in the chosen colour, and the Marker settings sit directly below the picture. Check boxes whose item the camera greys out (e.g. Focus Area Marker without Focus Assist Indicator) are greyed out as well.
- **NTSC / PAL area** (System > Country, first item of the first tab): switching it also moves the recording format to the closest frame rate of the new system (50p to 59.94p, 25p to 29.97p and back) with the values that go with it, as the camera does; the changed rows are marked.
- **Search and filter** (Ctrl+F): by name, ID or value; "changed only" shows everything that differs from the loaded file, "known only" hides undecoded IDs.
- **Import** (File > Import, Ctrl+I): take over all known differing values from any SCENE/ALL file of either model, or pick single parameters from a list. One undo step.
- **Recent files** (File menu): the last ten files, newest first; the last used tab and the window position are remembered, too.
- **Compare** (File > Compare…, Ctrl+D, or "Show differences" in the import dialog): side-by-side view of the current file and another file with readable menu paths such as `Paint/White Clip/White Clip Level` instead of IDs. Changed rows are coloured; Alt+Down / Alt+Up (or F8 / Shift+F8) jump to the next / previous difference, Ctrl+1 shows the full files, Ctrl+2 only the differences.
- **New** (Ctrl+N): neutral starting point for either model (not a factory reset).
- Undo/redo, changed values are marked, title bar shows unsaved changes.
- **About** (Help > About) shows the licenses of the components used ("Third-party licenses…"), also in the Windows build.
- Languages switchable at run time (View > Language): English (default), German, Spanish, French, Italian and Portuguese (Portugal and Brazil); High-DPI aware; day, night or system theme.
- Files are loaded defensively: size, line, ID and value limits reject malformed or hostile files.

## Download (Windows)

A ready-to-run Windows build is attached to each [release](../../releases): download the ZIP, unpack it and start `SonyConfigEditor.exe`. The program is not code-signed, so Windows SmartScreen may warn ("More info" > "Run anyway"), and a few virus scanners flag unsigned PyInstaller programs as suspicious (false positives). The release page lists the SHA-256 checksum so that you can verify the download, and the complete source code is in this repository.

## Installation from source

Python 3.10+ with Tkinter (included in the python.org installers; Debian/Ubuntu: `sudo apt install python3-tk`).

```
pip install customtkinter pillow
python SonyConfigEditor.py [file]
```

Pillow is only used for the logo in the About dialog. Settings (language, last folder, recent files, last tab, window position and size) are stored in your user config directory (put a `settings.json` next to the program for a portable setup).

## Usage

1. **Open** a SCENE or ALL file (Ctrl+O, or File > Recent files) or start a **New** one (Ctrl+N).
2. Change values; use the filter to find them. Greyed-out entries cannot be set in the current state.
3. Choose the **model** (FS7 / FS7M2) and **type** (SCENE / ALL) in the header if you want to convert.
4. Set the **file ID** (name, 16 characters) and **number** (000-999); **Save** (Ctrl+S) writes `NNN.SCENE` / `NNN.ALL` into the folder of the loaded file, **Save As** (Ctrl+Shift+S) lets you choose.
5. Copy the file to the camera's SD card and load it in the camera (Scene File / All File menu, see the camera manual for the folder).

Cine EI note: SCENE files exist only in Custom mode; in Cine EI mode only ALL files can be written.

## Status of the decoding

IDs are decoded by comparing files and the manuals. Decoded so far for the FS7M2 (ALL files): the Paint menu, most of Camera, Audio, VF (Display On/Off, Zebra, Peaking, Marker, parts of VF Setting), the first items of TC/UB, System (base setting, codec / rec format, country) and S&Q Motion; many of the remaining menus are still raw values. Each entry in `scene_parameters.json` / `all_parameters.json` carries a status (`confirmed`, `likely`, `hypothesis`); dropdown entries taken only from the manuals are marked "assumption". What is known and how it was found: [docs/FINDINGS.md](docs/FINDINGS.md); menu dependencies from the manuals: [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md). Camera test reports and sample files are welcome.

## Build an executable

- Windows: `build_exe.bat` -> `dist\SonyConfigEditor.exe` (needs `pip install pyinstaller`)
- Linux / macOS: `bash build_app.sh` (untested so far)

## Translations

`python -X utf8 -I tools/i18n_keys.py --missing` lists texts without translation. The translations (all except English) were made with AI assistance; review by native speakers is welcome. A new language is a new file `translations/<code>.json` (the English texts in the code are the keys; see `translations/de.json`).

## Contributing

The most useful help are camera files: before/after pairs in which exactly one setting was changed, with a short description. How to make them and where to send them: [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and translations are welcome, too.

## Development

Developed with the help of an AI coding assistant (Claude by Anthropic); all changes were reviewed and tested by the author.

## Contact

Questions, ideas and sample files: [GitHub Discussions](https://github.com/sonyconfigeditor/SonyConfigEditor/discussions). Camera test reports and anything private: sonyconfigeditor@gmail.com

## License

MIT, see [LICENSE](LICENSE). Third-party components: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Copyright (c) 2026 Lukas Himmelswanderer.
