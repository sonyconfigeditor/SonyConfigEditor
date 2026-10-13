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
