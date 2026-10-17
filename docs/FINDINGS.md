# Findings: Sony PXW-FS7 / PXW-FS7M2 SCENE and ALL files

What is known about the configuration files of the Sony PXW-FS7 ("Mk1") and PXW-FS7M2 ("Mk2"), and how sure we are. Sony does not document the format; everything here was found by comparing files that were saved on real cameras, and by reading the manuals. Status words used in the databases (`scene_parameters.json`, `all_parameters.json`):

- **confirmed**: shown by a file difference (one menu item changed on the camera) and/or the manual.
- **likely**: strong hint, not proven.
- **hypothesis**: a guess; treat it with care.

"Own files" and "sample files" below are files that are not part of this repository.

## Research status

- No public documentation or parser of the SCENE format was found (searches for parsers, editors, the `V01.00` header and parameter IDs). Community articles describe only the effect of SCENE files, not the format.
- The format was derived from sample files from both camera models. Every sample file round-trips byte-identically through the reader/writer.

## Container format (confirmed)

```
<md5 of everything after line 1>
V01.00^^^^^^^^^
<name, padded with ^ to 17 characters>
<model: PXW-FS7 | PXW-FS7M2>
<5-digit ID>=<value[,value...]>
...
%%%%
```

LF line endings, latin-1. SCENE files (`.SCENE`), ALL files (`.ALL`) and the user menu file (`.USER`) use the same container. Values are numbers or, in a few ALL entries, text.

## SCENE files and ALL files

- A SCENE file holds the *Camera* (ISO/gain/EI, shutter, auto exposure, noise suppression ...), *Paint* (black, gamma, knee, white clip, detail, matrix, multi matrix ...) and *White* items of the camera menu. The manuals list exactly which menu item belongs into which file type (appendix "items stored in files").
- An ALL file additionally holds almost everything else (audio, viewfinder, time code, recording, system ...). It is a superset of the SCENE file items. Not included: Wi-Fi credentials, clip operations, hours meter, white offset R/B.
- **The IDs of the two file types differ.** The scene items appear in the ALL file as a block in the same order, with additional items in between (offset grows: scene 00006/00007 = ALL 00024/00025, scene 00036/00037 = ALL 00068/00069, scene 00069 = ALL 00126 ...). `id_map.json` maps 101 scene IDs to ALL IDs (checked on file pairs of both models: all assigned pairs agree). 14 scene IDs have no counterpart.
- The IDs do not follow the menu order. They can only be assigned by comparing files and with the option lists of the manuals; the manuals do not list numeric IDs.
- **Recording mode:** SCENE files exist only in **Custom** mode. In **Cine EI** mode only ALL files can be written. Cine EI settings (exposure index, colour space, monitor LUT ...) therefore live in ALL files only.
- The ALL files of the Mk2 use the same IDs as the Mk1 plus seven new, still unknown ones (`00341`, `00472`-`00477`). An early assumption that the IDs shift between the models was wrong.

## How values are stored

| Item | Storage |
|---|---|
| Menu steps -99..+99 (aperture level, user matrix, detail, gamma levels ...) | step x 329.33 (limits stored as +32767 and, for gamma, -32768) |
| Black R/B | step x 330.16 (one data point) |
| Step Gamma | displayed value x 100 (0.45 -> 45; range 0.35 to 0.90) |
| White Clip level | 0.1 % units (1090 = 109.0 %), range 90.0 to 109.0 % |
| Skin Detail hue | -degrees x 182.04 (65536/360, negative sign) |
| Skin Detail width | degrees x 182.04 |
| Frame rate (ALL 00150) | numerator / denominator (30000/1001 = 29.97p) |
| Master Black | 41.351 per wheel click, 8 clicks per menu step (FS7M2; see below) |

Master Black (FS7M2, measured click by click): the file stores the wheel position, every value is a whole multiple of **41.351** (one click). The menu shows the click count divided by **8, cut towards zero**: -7..+7 clicks (-289..+289) show 0, -8 (-331) to -15 (-620) show -1, -16 (-662) starts -2, -24 (-992) starts -3, -40 (-1654) starts -5; the positive side is symmetric (+8 = +331 shows +1). Measured: -827 (-20), -662, -620, -331, -289, +289, +331, -992, -1613, -1778. The Mk1 values -1075, -1158, -1654 are multiples of the same unit (26, 28, 40 clicks) but do not fit the 8-click raster, so the Mk1 menu step width is not known yet. A range of 99 menu steps = 792 clicks is assumed (32767 / 41.351). The conversion maps displayed steps (`value_maps` in `scene_parameters.json`); an unknown raw value keeps the target model's state.

## What the manuals give us

- Option lists in index order (gamma select, preset select, multi matrix axes) give the value codes; value ranges and defaults (user matrix -99..+99, preset white 2100-10000 K, colour temperature 1500-50000 K).
- **ISO/gain/EI:** ISO values depend on the dynamic range (460 %: ISO 800-6400; 800 %: 1600-12500; 1300 % S-Log: 2000-16000; dB -3..18). Exposure index (Cine EI) 500-8000, default M = 1600, L = 800.
- **Shutter:** speed / angle / ECS / off; angles 5.6 ... 300 degrees; ECS frequency 23.99-8000 Hz.
- **ND filter (Mk2 only):** presets 1/4 ... 1/128 (electronic variable ND). The Mk1 has fixed ND only.
- **White:** preset white 2100-10000 K (3200 K); per memory A/B colour temperature, balance, R/B gain; shockless white, ATW speed. White data of a SCENE file is applied only when the scene white data setting is On.
- **Paint:** black, gamma (categories STD, HG, User, S-Log2, S-Log3; step gamma; master/R/G/B gamma), black gamma, knee, white clip, detail, skin detail, aperture, matrix, multi matrix (16 axes, hue and saturation -99..+99). Black gamma and knee saturation cannot be used together. Knee and black gamma are active with gamma category STD only. The manuals list User 1 to User 5 as user gammas.
- **Differences between the manuals (Mk1 / Mk2):** preset select has 5 entries on the Mk1 and BT.2020 additionally on the Mk2 (**only with a 4K/QFHD recording format**); the Mk2 has ND presets and auto ND in SCENE files, and output colour space, "Rec/Out EI applied", ND dial direction and camera ID in ALL files; ISO lists reach higher values on the Mk2; "scene white data" is a SCENE file item on the Mk1 and an ALL file item on the Mk2. The recording formats (resolution x frame rate) of the two manuals are identical (39 combinations): the Mk2 offers no additional formats.

## Mk1 versus Mk2 in SCENE files

- IDs only in Mk1 files: `00113`, `00153`, `00155`. Only in Mk2: `00179`-`00181` and the block `00159`-`00178`, which is fully populated in all Mk2 files.
- Different shape: `00097`, `00158`, `00160`. Different values: `00002`, `00008`, `00037`, `00068`, `00069`, `00136`-`00138`, `00144`, `00145`.
- Aperture setting (`00037`) is occupied on the Mk1; its Mk2 meaning was confirmed later (see below).

### Conversion rules (checked on the camera)

- A value is carried over if it exists in both models with the same number of fields and is valid for the target model (`_transfer` in `scene_parameters.json`).
- Model specific (kept at the target model's state): `00008` (Master Black, mapped by displayed step), `00097`, `00136`-`00138`, `00144`, `00145`, `00160`; `00158`: first field only; Mk1-only IDs stay stored for the way back.
- Values that cannot be transferred (for example BT.2020, Mk2-only IDs) stay stored in their own model profile and return when switching back.
- **Result:** SCENE files made for the Mk1 and converted to the Mk2 load on a real FS7M2 and show the intended master black, gamma and white clip. A conversion reproduces real Mk2 files up to camera- and state-specific IDs (master black, white memory, preset white, `00097`, `00136`-`00138`).
- Loading a SCENE file on the camera rewrites camera-owned values in the following saved file (white memories A/B, preset white, `00166`, `00147`); this fits "scene white data" in the manual. White clip is switched off by the camera with S-Log2/S-Log3, and `00097` field 3 is computed by the camera from the gamma.

## Parameters by menu

### Gamma

- Gamma **category** is a set of one-hot flags: scene `00017` STD, `00019` HG, `00078` User, `00022` S-Log2, `00143` S-Log3 (ALL: `00039`, `00041`, `00190`, `00044`, `00494`). Exactly one is 1.
- Gamma **select** has its own ID per category: scene `00018` STD (ALL `00040`), `00085` HG (ALL `00042`), user select ALL `00191` (User 4 = 3); S-Log2/S-Log3 have no sub-selection. Index = order of the manual's list (STD1..STD6 = 0..5, HG1-HG4, HG7, HG8 = 0..5).
- Gamma On/Off: scene `00023` / ALL `00045` (Off greys out the other gamma settings and keeps category and selection). Master gamma: scene `00024` / ALL `00046`; R/G/B gamma: ALL `00491`-`00493` (B gamma minimum stored as -32768). Step gamma: scene `00021` / ALL `00043`.
- **White clip:** setting scene `00068` / ALL `00125` (1 = On), level scene `00069` / ALL `00126`. The camera switches the setting off with S-Log2/S-Log3 and in Cine EI. (An earlier reading of ALL `00125` as a gamma flag was wrong.) The manual says the setting returns to On after a restart; permanently off is level 109 %.

### Black, aperture, matrix

- Black setting: ALL `00031` (0 = On, 1 = Off; the camera sets Off in Cine EI), master black scene `00008` / ALL `00028`, R/B black ALL `00029`/`00030`.
- Aperture: setting scene `00037` / ALL `00069`, level scene `00036` / ALL `00068` (confirmed on both models).
- Matrix setting scene `00005` / ALL `00023`; **Preset matrix** scene `00006` / ALL `00024` = `On/Off, preset` (Off greys out the preset select); **User matrix** scene `00007` / ALL `00025` = `On, Level, Phase, R-G, R-B, G-R, G-B, B-R, B-G`; **Adaptive matrix** scene `00115` / ALL `00307`.
- **Multi matrix** scene `00074` / ALL `00178`: 32 values, positions 0-15 = hue per axis, 16-31 = saturation per axis, in the menu order B, B+, MG-, MG, MG+, R, R+, YL-, YL, YL+, G-, G, G+, CY, CY+, B-. Area indication and the selected axis are not stored. Setting scene `00002` / ALL `00020`. With Matrix Off the multi matrix cannot be changed on the camera.

### Knee

Knee setting scene `00060` / ALL `00108` (1 = On), Auto Knee scene `00056` / ALL `00104` (field 1: 0 = On, 1 = Off; field 0 is unknown and constant), **Knee Point** scene `00057` / ALL `00105` (file value x 1000: 80000 = 80.0 %, manual range 75 to 109 %, default 90 %), **Knee Slope** scene `00058` / ALL `00106` (menu step x 329.33). Confirmed on the FS7M2 with a pair in which the gamma category was STD (Knee is active with STD only). The two other 90000/95000 values in ALL files (`00079`, `00085`) do not change with the Knee Point; they are probably knee points of other gamma groups (hypothesis). An earlier reading of `00060` as one of three STD flags was wrong. **Knee Saturation** setting scene `00061` / ALL `00109` (1 = On, the default; 0 = Off) and level scene `00059` / ALL `00107` (menu step x 329.33; +10 = 3293). The level keeps its value in the file when the setting is switched Off. Switching the gamma category from S-Log3 to STD also made the camera itself switch White Clip On, switch Preset Matrix On again (it had been set Off before; the preset value stayed; observed once, the rule behind it is unknown) and change ALL `00232` (field 6, 0 to 1, meaning unknown).

### Black Gamma

Black Gamma setting scene `00016` / ALL `00037` (1 = On), **Range** scene `00015` / ALL `00036` (High = 1, the default; Mid = 2; Low = 3; all confirmed, FS7M2 rounds 13, 35, 36), **Master Black Gamma** scene `00011` / ALL `00032` (+5 is stored as 5, not multiplied by 329.33 like most menu steps; one data point, negative values unverified). Confirmed on the FS7M2 with gamma category STD and Knee Saturation Off; the manual says Black Gamma works with category STD only and cannot be used together with Knee Saturation (the program locks both against each other).

### Offset White (Paint menu)

The manual lists three groups (white memory A, B and ATW) with Offset White On/Off, Warm Cool and Warm Cool Balance (-99..+99); all are stored in scene and ALL files. Confirmed on the FS7M2 for A and B: scene `00149` / ALL `00501` holds the three On/Off flags (`<A>`, `<B>`, `<ATW>`, all three confirmed), **Warm Cool / Balance `<A>`** in scene `00150` / ALL `00502` and **`<B>`** in scene `00154` / ALL `00508`. The scale is **330.16 per step** (like R/B Black): +5 = 1651, +10 = 3302, +25 = 8254. The values are finer than the menu step (for example -1816 for a displayed -5, 3467 for +10): the camera shows the step cut towards zero. **ATW**: Warm Cool / Balance `<ATW>` are in scene `00152` / ALL `00505` (confirmed: +15 and -16 = 4952 and -5282); the Offset White `<ATW>` flag is the third field of `00149` (confirmed in a later round: `1,1,0` to `1,1,1`); the camera keeps the ATW values while the flag is Off. **White Switch<B> (Memory / ATW)** is scene `00118` / ALL `00312` (0 = Memory, 1 = ATW; likely). The camera greys the menu out unless the WHT BAL switch is on a white memory (A, B or ATW); the switch position is not stored in the file.

### Detail and skin detail

- Detail setting scene `00044` / ALL `00088`; level `00045`, H/V ratio `00046`, crispening `00047`, level depend setting `00043` and level `00042`, frequency `00053` (ALL `00089`-`00091`, `00087`, `00086`, `00097`). ALL files hold a second copy of the detail values without a scene counterpart (hypothesis).
- Knee aperture setting `00049`, level `00048`, limit `00052`, white limit `00050`, black limit `00051`, V black limit `00054`, V detail creation `00055` (NAM = 0, G = 1, Y = 3, G+R probably 2).
- **Skin detail** scene `00025` / ALL `00054`: `Setting, Level, Saturation, Hue, Width` in one value; width default 40 degrees.

### White memories

Scene `00144` / `00145` = memory A / B (R gain, B gain); `00164` / `00165` hold the same two values plus the colour temperature; further memory slots follow (`00166`-`00181`, probably per ND slot). Preset white (K) = first value of `00158`. These values belong to the camera, not to the look.

## ALL files: modes, formats and codecs

### Shooting mode and colour space

- **Shooting Mode** = ALL `00418` (0 Custom, 1 Cine EI, likely). Switching to Cine EI also changes `00031` (black setting), `00423` (colour space), `00023` (matrix Off), `00028` (master black 0), `00069` (aperture Off), `00499`, `00041`, and others; the camera does this itself.
- **Colour space** = `00423`: 0 = Matrix (Custom), 2 = S-Gamut/S-Log2, 4 = S-Gamut3.Cine/S-Log3, 5 = S-Gamut3/S-Log3 (1 and 3 unknown). In Cine EI the gamma follows from the colour space; no gamma ID changes.
- In Cine EI the Paint menu is greyed out on the camera. Other Cine EI restrictions of the manual: no gain (exposure index instead), no automatic white balance, no SCENE file, RAW recording only in Cine EI.

### Video format (ALL `00150`)

- Fields 0-3: width, height, frame rate denominator, numerator. Field 4: scan (1 = progressive, 0 = interlaced; frame rates up to 30p do not exist interlaced).
- Field 14 is a list index of the format inside a codec; fields 7, 9, 11, 12, 13 carry the codec/profile entry.
- **Codec index** (field 16 = `00175` position 42): 0 XAVC-I, 1 XAVC-L, 2 MPEG HD422, 6 RAW, 7 RAW & XAVC-I, 8 RAW & XAVC-L, 9 RAW & MPEG HD422, 10 ProRes 422 HQ, 11 ProRes 422 (3-5 unused).
- RAW is stored externally only; `00150` describes the internally recorded format. The **RAW output format** = field 17 (0 = 4096x2160 59.94p, 1 = 4096x2160 29.97p, 3 = 2048x1080 59.94p; 2, 4, 5 derived from the order of the manual's list; the same number means the PAL counterpart with 50p/25p), mirrored in `00175` position 43.
- **Imager scan mode** = `00338` (0 Normal, 1 2K Full, 2 2K Center); `00446` is related to RAW 2K Center. RAW 4096x2160 requires Normal; RAW 2048x1080 requires 2K Full or 2K Center; with a 2K scan mode the recording resolution is limited to 2K.
- Companion values that move with the format and are set together with it: `00175` (positions 40, 42, 44, 49, 51, 52), `00454` (second field 2 if more than 30 frames per second), `00426`, `00340`, `00282`, ProRes flags `00173` field 1 and `00407`, `00338`/`00446`. `00170` and `00283` depend on history and are not set.
- 39 further formats of the manuals (NTSC and PAL) are offered as marked assumptions: only resolution, frame rate and scan are set. The 35/25 Mbps variants are missing because their field is unknown.

### S&Q Motion

`00152` field 0 = S&Q setting (On/Off), `00151` field 0 = S&Q frame rate (default 60, 120 with a 2K scan mode), second field probably the high frame rate mode. Switching it on makes the camera change `00150` field 17 (to 3), `00175` position 43 and `00158` (to 2). According to the manual: 1 to 60 fps, with high frame rate mode (XAVC-L) 72-180 fps (PAL up to 150), RAW only in 2K with 120/240 (NTSC) or 100/200 (PAL), XAVC-I only up to 60. The limits per codec/region/scan mode are not modelled yet.

### Clip menu

- `00285` = clip name (title prefix, text); `00181`-`00183` = camera ID, reel number, camera position (likely).
- The running clip number (**Number Set**) is **not stored** in the ALL file: the camera counts it internally.

## Greyed-out options

Rules from the manuals and camera observations are stored as `requires` / `_locks` in the databases: RAW formats only in Cine EI, RAW 4096/2048 and scan mode, BT.2020 only with 4K/QFHD, no interlaced rates up to 30p, white clip with S-Log, sub-settings with their On/Off switch Off (gamma, black, matrix, multi matrix, detail, level depend, knee aperture, aperture), the Paint menu in Cine EI. Menu dependencies found in the manuals are listed in the project notes.

## Open questions

- Gamma User select in SCENE files; knee and black gamma IDs (the three STD-only flags `00060`, `00068` and one more are probably knee, auto knee and knee saturation).
- High frame rate mode and the limits of the S&Q frame rate.
- Codec indices 3-5; RAW output values 2, 4, 5 (derived only).
- Gain/ISO, exposure index, monitor LUT, high/low key, noise suppression and white balance fixed values in Cine EI (IDs unknown).
- The seven new ALL IDs of the Mk2.
- Many constant 0/1 flags and long runs of zeros in ALL files cannot be assigned without changing one menu item at a time on the camera.
- All statements about the Mk2 are limited to what was tested on one FS7M2 camera; behaviour with other firmware versions is unknown.

Knee Setting (scene `00060` / ALL `00108`) and Black Gamma Setting (scene `00016` / ALL `00037`) are available in gamma category STD only. The camera switches both off when STD is left (HG, User, S-Log2, S-Log3) and restores the state STD had when it is chosen again (FS7M2 rounds 25-30). Preset Matrix is not changed by a category switch.

Auto Knee: ALL `00232` field 6 mirrors it (1 = Auto Knee Off, 0 = On; no exception in 50 files), and `00104` field 0 was 0 in one file only (Knee Setting On and Auto Knee On), otherwise 1 (hypothesis). Preset Matrix is not changed by gamma category switches, Knee changes or a power cycle of the camera (FS7M2 rounds 24-34).

ISO/Gain/EI (FS7M2, ALL files): `00389` Mode (0 = ISO, 1 = dB); dB gain per switch position <L>, <M>, <H> in `00399`-`00401` (index = dB / 3 + 1: 1 = 0 dB, 3 = 6 dB, 4 = 9 dB, 5 = 12 dB; the manual lists -3 to 18 dB); ISO per switch position as a position in the manual's ISO list of the dynamic range, one triplet per range: `00390`-`00392` (460 %), `00393`-`00395` (800 %, confirmed: 2 = ISO 2500, 7 = ISO 8000), `00396`-`00398` (1300 %). The defaults 0, 3, 6 match the manual's defaults.

ND Filter presets (FS7M2): ALL `00280` / scene `00097`, fields 0 to 2 = Preset 1 to 3, each the denominator of the ND fraction (4, 8, 16, 32, 64, 128 = 1/4 to 1/128); fields 3 to 5 are unknown. The Mk1 has no variable ND (`0,0,0,4096`).

Auto Exposure (FS7M2, in All and Scene files): Level = scene `00081` / ALL `00221` (two fields: the second is the level x 100, -200 to +200 in steps of 25), Speed = `00082` / `00222` (the menu step), Mode = `00086` / `00265` (1 = Standard, 2 = Backlight). The Gamma User select is scene `00121` / ALL `00191`.

AGC: scene `00079` / ALL `00235` (1 = On; ALL `00232` field 4 mirrors it). AGC Limit: one list position per dynamic range, scene `00161`-`00163` / ALL `00456`-`00458` (460 %, 800 %, 1300 %); the manual's lists have six entries and the default position is 4; the limit is greyed out in the camera menu while AGC is Off. Mode: 1 = Standard, 2 = Backlight, 3 = Spotlight.

A.SHT Limit (Auto Shutter limit): scene `00084` / ALL `00225`, the denominator of the exposure time (default 2000 = 1/2000). Detect Window: `00088` / `00267` (1 to 6). Auto ND Filter: field 4 of the ND value `00097` / `00280` (0 = Off, 1 = On).

Auto Shutter: scene `00090` / ALL `00269` (1 = On). Clip High Light: `00087` / `00266` (1 = On). Detect Window Indication: `00089` / `00268`, stored inverted (0 = On, 1 = Off, found by elimination).

Focus (FS7M2, All files only, likely): Focus Area = ALL `00460` field 0 (0 = Wide, 1 = Center; Flexible Spot = 2 is an assumption; fields 1 and 2 unknown). AF Assist = ALL `00258` (1 = On). Both were changed in the same round, so the assignment rests on the value shapes.

Shutter (FS7M2, likely): scene `00160` / ALL `00459`, field 0 = Mode (0 = Speed, 1 = Angle; ECS = 2 and Off = 3 assumed), field 1 = position in the Shutter Angle list (5.6, 11.2, 22.5, 45, 90, 120, 144, 150, 172.8, 180, 216, 300 degrees; 180 = 9, 216 = 10). Fields 2 to 6 unknown.

Shutter mode: ECS = 2 (confirmed). ECS Frequency is field 3 of the same value (563 -> 559 when changing from about 50.1 to 49.77 Hz); the coding is a hypothesis (about 11.23 per Hz) and needs a round with known frequencies.

Shutter Speed: field 2 of the same value is the position in the Shutter Speed list of the current frame rate (25P: 1/50 = 4, 1/25 = 3; likely). ECS Frequency (field 3): 559 = 49.77 Hz, 613 = 55.02 Hz, roughly linear (hypothesis). Field 6 moves with the speed (7 -> 6), meaning unknown.

Noise Suppression: Setting scene `00003` / ALL `00021` (1 = On), Level `00004` / `00022` (1 = Mid, 2 = High; Low = 0 assumed).

ECS Frequency (field 3 of ALL `00459`, 25P, likely): v = floor(1125 - 28125 / f), where 1125 is the total line count of an HD frame and 28125 = 1125 x 25; inverse f = 28125 / (1125 - v). Checked with 34.00, 49.77 and 55.02 Hz. Other frame rates not checked.

Confirmed by a single-change round: AF Assist = ALL `00258` (1 = On); Noise Suppression Level Low = 0; Shutter Mode Off = 3. Focus Area = ALL `00460` follows by elimination (likely).

Focus Area: ALL `00460` field 0 (0 = Wide, 1 = Center, 2 = Flexible Spot; confirmed). Focus Area (Push AF): ALL `00461` field 0 (0 = Center, 1 = Flexible Spot; likely, changed together with Focus Area). Fields 1 and 2 of both stay 0 (the spot position is not set in the menu).

Color Bars: Type = ALL `00052` (0 = ARIB, 1 = SMPTE; 75% = 2 and 100% = 3 assumed). The Color Bars Setting (On/Off) is not stored in either file type.

Color Bars Type 75% = 2 (confirmed). Flicker Reduce (All file only, likely): Mode = ALL `00227` (0 = Auto, 1 = On; Off = 2 assumed), Frequency = ALL `00228` (0 = 50 Hz, 1 = 60 Hz); both were changed in the same round.

Color Bars Type 100% = 3 (confirmed). Flicker Reduce: `00227` and `00228` both went 1 -> 0 with Frequency 50 Hz and Mode Off; Mode Off = 0 (not 2), so the assignment of the two IDs and the Auto value are still open (a round with only the Frequency changed is needed).

Flicker Reduce Frequency = ALL `00228` (0 = 50 Hz, 1 = 60 Hz; confirmed by a single change). Mode = `00227` by elimination (0 = Off, 1 = On; Auto = 2 assumed).

Flicker Reduce Mode is spread over two ALL values: `00226` (Auto flag) and `00227` (active): Off = 0 / 0, On = 0 / 1, Auto = 1 / 1 (confirmed by rounds 60, 61 and 63; the earlier assumption Auto = 2 was wrong).

All file only (likely, assigned by the changed values): SteadyShot `00229` (0 = Off, 1 = SteadyShot; Active SteadyShot = 2 assumed), Handle Zoom Zoom Speed Type `00359` (0 = Fix, 1 = Variable; Off = 2 assumed), Video Light Set `00305` (0 = Power Link, 2 = Rec Link + Stby; Rec Link = 1 assumed).

SteadyShot: the option Active SteadyShot can be greyed out in the camera menu (depends on the attached lens; the manual gives no per-option condition), so its value (2) is still unverified.

Confirmed by single changes: Video Light Set `00305` (0 = Power Link, 1 = Rec Link, 2 = Rec Link + Stby), Zoom Speed Type `00359` (0 = Fix, 1 = Variable, 2 = Off). SteadyShot `00229` (0 = Off, 1 = SteadyShot) follows by elimination.

Handle Zoom Zoom Speed: ALL `00231` field 0 (1 to 8, default 3; likely, confirmed by a single change). Fields 1 and 2 unknown.

Factory state of the FS7M2 (full reset, PAL region): UHD 3840x2160 50p, gamma category STD with STD5 R709 and the S-Log3 flag (scene `00143` / ALL `00494`) set as well, dynamic range and gain at their defaults (gain mode dB, L/M/H = 0 / 6 / 12 dB, ISO index 0 / 3 / 6 per range), Auto Exposure Level 0, ND presets 1/4, 1/16, 1/64, Master Black 0, Matrix and Multi Matrix at zero, White Clip level 105 %, Knee Setting On, Auto Knee On. The clip name is derived from the serial number of the camera; it is replaced in the exported templates.

Audio > INPUT1 / INPUT2 MIC Reference: ALL `00015` / `00016`, stored as the dB value (-60, -50, -40; factory -50). Audio menu items are stored in ALL files only (the manual lists them as not saved in SCENE files).

Audio input select: CH1 = ALL `00369`, CH2 = `00370`, two fields (kind of source: 2 = INPUT1/INPUT2 connector, 0 = Internal MIC; number of the input). Kind of source: 2 = INPUT1/INPUT2 connector, 0 = Internal MIC, 5 = Shoe; INPUT1 = `2, 1`, INPUT2 = `2, 2`, CH1 Internal MIC = `0, 1`, CH1 Shoe 1 = `5, 1`, CH2 Internal MIC = `0, 2`. CH1 / CH2 Wind Filter = field 0 of `00239` / `00240` (0 Off, 1 On).

Audio input select, CH2-CH4: CH2 Shoe 2 = `5, 2` in `00370`. CH3 = ALL `00427`, CH4 = `00428`, same two-field coding (Off = `12, x`, Internal MIC = `0, x`, Shoe = `5, x`; field 1 = channel; CH3 Internal MIC `0, 3` and CH4 Shoe 2 `5, 4` seen, CH3 Shoe 1 and CH4 Internal MIC assumed). For microphones and shoe inputs field 1 is the channel, for the INPUT1/INPUT2 connectors the number of the connector.

Audio level control: ALL `00142` (CH3) and `00143` (CH4), 0 = Auto, 1 = Manual (CH1 and CH2 have hardware switches and no menu item); input level of CH3 / CH4: ALL `00438` / `00439`, 0 to 99 (factory 49). File > Scene File > Scene White Data: ALL `00304`, 0 = Off, 1 = On; the item only controls whether the white balance data of a SCENE file is applied when it is loaded, the SCENE file itself always contains these values.

Audio wind filter CH3 / CH4: field 0 of ALL `00429` / `00430` (0 Off, 1 On). Audio Output > Monitor CH: ALL `00440`, 0 = CH1/CH2 (factory), 2 = MIX ALL; the manual order CH1/CH2, CH3/CH4, MIX ALL, CH1, CH2, CH3, CH4 suggests 1 = CH3/CH4 and 3-6 = CH1-CH4 (not seen). `00374` (16 flags) changed together with the monitor channel; the camera probably derives it from the channel selection (hypothesis).

Audio Output: Monitor Volume = field 0 of ALL `00137` (0 to 15, factory 7; field 1 = 15 unknown), Alarm Volume = ALL `00375` (0 to 7, factory 4), Monitor CH CH3 = 5 in `00440`.

Audio input: Audio Input Level = ALL `00371` (0 to 99, factory 99); Limiter Mode = switch `00146` (0 Off, 1 On) plus level `00147` (dB value, 0 when off, -12 seen); AGC Spec = `00144` (dB value, factory -6, -9 seen). 1 kHz Tone on Color Bars = `00053` (next to Color Bars Type), stored inverted: 1 = Off, 0 = On.

Audio AGC mode: field 0 of ALL `00141` (CH1&2) and `00431` (CH3&4), 0 = Mono, 1 = Stereo. Channel level selection CH1-CH4: ALL `00372`, `00373`, `00432`, `00433` (factory 2 each): 0 = Audio Input Level, 1 = the channel's own input level ('CH3 Input Level' seen; 'Side' for CH1/CH2 assumed), 2 = both combined (factory state; 'Level+Side' confirmed for CH2); the Mk2 offers these three entries without an XLR adapter, in this order.

Audio output: Headphone Out = ALL `00139` (0 Mono, 1 Stereo), Output Limiter = `00376` (0 Off, 1 On), HDMI Output CH = `00441` (0 CH1/CH2, 1 CH3/CH4); the first two were changed together and are assigned by their neighbours in the file and the menu order. CH2 / CH4 Level (`00373` / `00433`) were changed to Audio Input Level (0).

VF > Display On/Off: the switches are the first 42 values of ALL `00175` in the order of the menu (Setting first): 0 = shown, 1 = hidden; the codec index follows at position 42. Seen: Clip Name = position 33, Gamma = 30 (menu order confirmed at both ends); Color Temp., Battery Remain, Timecode and Audio Level Meter are among positions 4, 6, 7 and 10 (not yet assigned).

VF > Display On/Off, continued: the list starts with Shutter Setting at position 0 (the item Setting is not in it); Shutter Setting = 0, Gain Setting = 2 (ND Filter Value = 1 in between), Color Temp. = 4, Frame Rate / Interval = 5, Battery Remain = 6, Timecode = 7, Audio Level Meter = 10, Gamma = 30, Clip Name = 33. The positions follow the menu order only roughly: some menu items hold more than one value.

VF > Display On/Off, round 3: ND Filter Value = 1, Rec/Play Status = 3, Frame Rate / Interval = 5, Audio Manual = 8 and 9 (two values), Media Status = 11, Focus Position = 12, Zoom Position = 14 (the three-state items Focus Position and Zoom Position hold 2 when switched Off), Timecode Lock = 31. ALL `00231` field 2 (Zoom Speed row) changed from 0 to 2 in the same round.

VF > Display On/Off, status: the switches of the remaining elements (Auto ND Filter, AE Mode, White Balance Mode, Rec Format, Wi-Fi Condition, Clip Number, GPS, Level Gauge, ...) are in `00175` too, but not all in the order of the menu (one lies at position 55, behind the recording format values); only positions 0 to 14, Gamma (30), Timecode Lock (31) and Clip Name (33) are assigned so far.

VF > Zebra: ALL `00132` = Zebra 1 (field 0 on flag, 1 level in %, 2 aperture level in %), `00133` = Zebra 2 (field 0 on flag, 1 level in %); `00480` / `00481` are identical copies. Zebra Select is derived: 1 = Zebra 1 on and Zebra 2 off, 2 = the other way round, Both = both on (round: Select 1 -> Both changed only the Zebra 2 flag from 0 to 1). The switch Setting (Zebra on/off) is not stored in the file. Levels are stored 1:1 in % (81 % -> 81).

VF > Peaking: ALL `00120` (7 fields): field 2 Color Peaking Level (0 to 99, 1:1), field 3 Color (0 B&W, 2 Yellow seen; 1 Red and 3 Blue by the manual's order), field 4 Peaking Type (0 Normal, 1 Color), field 6 Normal Peaking Level (0 to 99, 1:1); fields 0, 1, 5 (1, 3, 0) unknown, the switch Setting is not stored.

VF > Marker: Center Marker = ALL `00075` (on flag) + `00076` (type 0 to 3 = marker 1 to 4); Safety Zone = `00078` (0 Off, 1 On); Safety Area = `00079` (percent x 1000: 90000, 92500, 95000); Marker Color = `00510` (0 White, 5 Red; the order of the manual's list). The switch Setting is not stored. SCENE `00157` is paired with `00510` in the ID map by equal value; unverified.

VF > Marker, aspect: Aspect Marker = ALL `00080` (on flag) + `00081` (style, 1 = Mask), Aspect Select = `00082` (0 = 4:3, 8 = 2.35:1; the other choices are not seen), Aspect Mask = `00083` (0 to 15), Aspect Safety Area = `00085` (percent x 1000). SCENE files do not hold the marker color (SCENE `00157` stayed 0 with the color Red): the earlier pairing with `00510` was a coincidence.

VF > Marker, user box: User Box = ALL `00323` (0 Off, 1 On), Width = `00324` (3 to 479, factory 240), Height = `00325` (3 to 269, factory 135), H Position = `00326` (-476 to +476, factory 0); the vertical position is probably `00327`.

VF, rounds 89 and 90: Aspect Safety Zone = ALL `00084` (0 Off, 1 On), User Box V Position = `00327` (-266 to +266), 100% Marker = `00360`, Guide Frame = `00245` (0 Off, 1 On), Aspect Select: 7 = 1.85:1, 8 = 2.35:1 (4:3 = 0), VF Setting > Brightness = `00243` (-99 to +99, 1:1). The switch of the video signal monitor possibly sits in `00175` position 38 (hypothesis).

TC/UB, first round: HDMI TC Out = ALL `00260` (0 Off, 1 On, likely). Timecode Mode (Preset / Regen / Clock) and Run (Rec Run / Free Run) changed only ALL `00158` (1 -> 0 with Preset / Rec Run -> Regen / Free Run; Regen locks Run; the value is also 2 with S&Q Motion on); TC Format is locked (NDF only) in PAL-based formats.

TC/UB, second round: ALL `00158` holds timecode mode and run together: 0 = Regen, 1 = Preset with Rec Run, 2 = Preset with Free Run (also 2 with S&Q Motion on); `00176` = TC Display Select (0 Timecode, 3 Duration seen); `00283` = Users Bit Mode (0 Fix, 1 Time).

VF > Peaking, Setting: field 0 of ALL `00120` is the switch Setting, stored inverted (1 = Off, 0 = On). After a second full reset of the camera the files differ from the first factory file in `00454` (second field 1 -> 2) and `00494` (1 -> 0); both belong to the camera state, not to the setting that was changed (after the reset only the time and date were set, so the factory state of these two values is not unique).

VF > Display On/Off, after the second reset: SteadyShot = position 16 and Focus Mode = 17 of ALL `00175` (Focus Area Indicator = 19); HXR-IFR5 Rec Control, Focus Area Ind. (Push AF) and Focus Indicator lie at 49, 53 and 54 (not separated; position 49 changes the other way round, 1 -> 0).

VF > Display On/Off, set arithmetic over several rounds: Focus Mode = 17, Auto Shutter = 20, Focus Indicator = 19 of ALL `00175` (certain); the remaining switches are known as pairs: SteadyShot / Focus Area Indicator = 16 / 53, HXR-IFR5 Rec Control / Push AF = 49 / 54, AGC / Auto Iris = 21 / 22, Auto ND Filter / AE Mode = 23 / 55, White Balance Mode / Rec Format = 24 / 27, Wi-Fi Condition / Clip Number = 28 / 34. The positions do not follow the order of the menu.

VF > Display On/Off, pairs separated: SteadyShot = 16, Focus Mode = 17, Focus Indicator = 19, Auto Shutter = 20, AGC = 21, Auto Iris = 22, AE Mode = 23, White Balance Mode = 24, Rec Format = 27, Wi-Fi Condition = 28, Clip Number = 34, Focus Area Indicator = 53, Push AF = 54, Auto ND Filter = 55, HXR-IFR5 Rec Control = 49 (the only switch that is 1 when shown). The positions after 41 belong to the same list.

VF > Display On/Off, last group: GPS = position 39 of ALL `00175` (shown = 1, like HXR-IFR5 Rec Control), Notice Message = 47 (by elimination); Auto Exposure Level, SDI/HDMI Rec Control, Focus Assist Indicator, Video Level Warning and Level Gauge occupy 25, 29, 35, 36 and 50 (order not separated yet).

VF > Display On/Off, more: Audio Manual = position 9, Lens Info = 40 (three-state: 0 Meter, 2 Off), Focus Area Marker = 37; Auto Exposure Level, Focus Assist Indicator and Level Gauge lie on 8, 35 and 50, SDI/HDMI Rec Control and Video Level Warning on 25, 29 and 36 (order not separated yet).

VF > Display On/Off, more: Auto Exposure Level = position 50, Video Level Warning = 29, Notice Message = 47 (confirmed), position 38 = Setting of Video Signal Monitor (0 Off, 2 Vector). Focus Assist Indicator and Level Gauge lie on 8 and 35, SDI/HDMI Rec Control on 25 and 36. VF Setting > Color Mode = ALL `00246` (0 Color, 1 B&W).

VF > Display On/Off, more: SDI/HDMI Rec Control = position 25; Video Signal Monitor Setting at 38 is 0 Off, 1 Waveform, 2 Vector. Focus Assist Indicator and Level Gauge are still 8 and 35 in unknown order; position 36 is not assigned. VF > Peaking > Frequency = field 5 of ALL `00120` (0 Normal, 1 High).

VF > Display On/Off, completed: Level Gauge = position 8, Focus Assist Indicator = 35, master switch Setting = 48 (0 On, 1 Off); position 36 is not assigned. TC/UB > Timecode Mode: Clock = 3 in ALL `00158` (0 Regen, 1 Preset+Rec Run, 2 Preset+Free Run, 3 Clock).

VF > Marker > Setting = ALL `00074` (1 On, 0 Off). VF > Display On/Off > Focus Area Marker occupies positions 36 and 37 of `00175` (selectable only while Focus Assist Indicator is On), so position 36 is no separate item.

TC/UB > Users Bit > Setting = ALL `00284`: four bytes, each pair of hex digits stored as one decimal number with a trailing comma (`12 34 56 78` = `18,52,86,120,`). VF > Peaking > Color: Blue = 3 (field 3 of `00120`). Display On/Off master switch Setting = position 48 of `00175` (confirmed). TC Display > Display Select has three entries in the menu (Timecode, Users Bit, Duration); Timecode = 0 and Duration = 3, the code of Users Bit is not seen yet.

TC/UB > TC Display > Display Select: Timecode = 0, Users Bit = 1, Duration = 3 (ALL `00176`). VF > Peaking > Color: Red = 1, Yellow = 2, Blue = 3, B&W = 0. The Preset time of TC/UB > Timecode > Setting is not stored in the ALL file (entering 01:02:03:04 changed no value). Zebra Select Both switches Zebra 2 on (`00133` and its copy `00481`, first value 1).

VF > Marker: Aspect Select 1.66:1 = 6 (ALL `00082`: 0 4:3, 6 1.66:1, 7 1.85:1, 8 2.35:1, 9 2.4:1 assumed); Aspect Marker Line = `00080` 1 with `00081` 0 (Mask = `00081` 1).
